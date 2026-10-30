import cv2
import math
import time
import pandas as pd
import mediapipe as mp
import tkinter as tk
import json

from tkinter import ttk, messagebox, simpledialog
from pathlib import Path
from PIL import Image, ImageTk

CAMERA_INDEX = 0

POINTS = {
    "NARIZ_REF": 1,
    "OJO_IZQ": 133,
    "OJO_DER": 362,
    "BOCA_SUP_EXT": 0,
    "BOCA_INF_EXT": 17,
    "BOCA_SUP_INT": 13,
    "BOCA_INF_INT": 14,
    "BOCA_IZQ": 61,
    "BOCA_DER": 291,
    "BARBILLA": 152,
    "MANDIBULA_IZQ": 148,
    "MANDIBULA_DER": 377
}

TRACKED_POINTS = [
    "BOCA_SUP_EXT", "BOCA_INF_EXT", "BOCA_SUP_INT", "BOCA_INF_INT", 
    "BOCA_IZQ", "BOCA_DER", "BARBILLA", "MANDIBULA_IZQ", "MANDIBULA_DER"
]

SYLLABLES = ["TA", "TE", "TI", "TO", "TU", "SA", "SE", "SI", "SO", "SU", "RA", "RE", "RI", "RO", "RU"]

class OrofacialApp:
    def __init__(self, root):
        self.root = root
        self.root.withdraw() 

        self.participant_name = simpledialog.askstring("Nuevo Participante", "Ingrese nombre del participante:")
        if not self.participant_name or not self.participant_name.strip():
            self.root.destroy()
            return
            
        self.participant_name = self.participant_name.strip().replace(" ", "_")
        try:
            script_dir = Path(__file__).resolve().parent
        except NameError:
            script_dir = Path.cwd() 
            
        self.folder_path = script_dir / self.participant_name
        self.folder_path.mkdir(exist_ok=True)

        self.root.deiconify() 
        self.root.title(f"Registro - {self.participant_name}")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.cap = cv2.VideoCapture(CAMERA_INDEX)
        self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False, 
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        self.running = True
        self.is_recording = False
        self.current_syllable = None
        self.current_filename_base = None
        self.video_writer = None
        self.start_time = 0
        self.current_recording_data = [] 
        self.recorded_syllables = set()
        
        self.current_normalized_points = {} 
        self.neutral_data = None 

        self.is_capturing_neutral = False
        self.neutral_frames_collected = 0
        self.neutral_buffer = {pt: {"x": 0.0, "y": 0.0} for pt in TRACKED_POINTS}
        self.NEUTRAL_SAMPLES_NEEDED = 30 

        self.build_interface()
        self.update_camera()
        self.root.bind('<space>', lambda e: self.toggle_recording())

    def build_interface(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(padx=10, pady=10, fill="both", expand=True)

        video_frame = ttk.Frame(main_frame)
        video_frame.grid(row=0, column=0, padx=10)
        
        self.video_label = ttk.Label(video_frame)
        self.video_label.pack()

        self.recording_indicator = ttk.Label(video_frame, text="", font=("Arial", 14, "bold"))
        self.recording_indicator.pack(pady=5)

        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=0, column=1, sticky="n", padx=10)

        self.btn_neutral = ttk.Button(
            control_frame, 
            text="1. Calibrar Rostro Neutral (1 seg)", 
            command=self.start_neutral_capture
        )
        self.btn_neutral.pack(fill="x", pady=(0, 15), ipady=5)

        ttk.Label(control_frame, text="2. Sílabas a grabar:").pack(pady=(0, 5))

        self.syllable_listbox = tk.Listbox(control_frame, height=15, font=("Arial", 12))
        self.syllable_listbox.pack(fill="x", pady=5)
        for syl in SYLLABLES:
            self.syllable_listbox.insert(tk.END, f"[ ] {syl}")
        self.syllable_listbox.selection_set(0) 

        self.record_button = ttk.Button(
            control_frame, text="Grabar (Espacio)", 
            command=self.toggle_recording, state="disabled" 
        )
        self.record_button.pack(fill="x", pady=15, ipady=10)

        self.finish_button = ttk.Button(
            control_frame, text="Finalizar", command=self.finish_session
        )
        self.finish_button.pack(fill="x", pady=5)

    def start_neutral_capture(self):
        if not self.current_normalized_points:
            messagebox.showwarning("Atención", "No se detecta rostro.")
            return
        
        self.btn_neutral.config(text="Calibrando...", state="disabled")
        self.is_capturing_neutral = True
        self.neutral_frames_collected = 0
        self.neutral_buffer = {pt: {"x": 0.0, "y": 0.0} for pt in TRACKED_POINTS}

    def process_neutral_calibration(self):
        if self.neutral_frames_collected < self.NEUTRAL_SAMPLES_NEEDED:
            for pt in TRACKED_POINTS:
                self.neutral_buffer[pt]["x"] += self.current_normalized_points[pt]["x"]
                self.neutral_buffer[pt]["y"] += self.current_normalized_points[pt]["y"]
            self.neutral_frames_collected += 1
            self.recording_indicator.config(text=f"Calibrando: {self.neutral_frames_collected}/{self.NEUTRAL_SAMPLES_NEEDED}", foreground="blue")
        else:
            self.neutral_data = {}
            for pt in TRACKED_POINTS:
                self.neutral_data[pt] = {
                    "x": self.neutral_buffer[pt]["x"] / self.NEUTRAL_SAMPLES_NEEDED,
                    "y": self.neutral_buffer[pt]["y"] / self.NEUTRAL_SAMPLES_NEEDED
                }
            
            self.is_capturing_neutral = False
            self.btn_neutral.config(text="✓ Rostro Neutral Promediado")
            self.recording_indicator.config(text="")
            self.record_button.config(state="normal")
            
            with open(self.folder_path / f"{self.participant_name}_neutral_ref.json", "w") as f:
                json.dump(self.neutral_data, f, indent=4)

    def toggle_recording(self):
        if not self.neutral_data or self.is_capturing_neutral: return 
            
        if not self.is_recording:
            sel = self.syllable_listbox.curselection()
            if not sel: return
            self.current_syllable = SYLLABLES[sel[0]]
            self.current_recording_data = [] 
            
            # Buscar el numero de repeticion disponible para no sobrescribir
            repeticion = 1
            while True:
                video_name = f"{self.current_syllable}_R{repeticion:02d}.avi"
                if not (self.folder_path / video_name).exists():
                    break
                repeticion += 1
                
            self.current_filename_base = f"{self.current_syllable}_R{repeticion:02d}"
            
            video_path = str(self.folder_path / f"{self.current_filename_base}.avi")
            self.video_writer = cv2.VideoWriter(video_path, cv2.VideoWriter_fourcc(*'XVID'), 30.0, (self.frame_width, self.frame_height))
            
            self.is_recording = True
            self.start_time = time.perf_counter()
            self.record_button.config(text=f"Detener {self.current_syllable} (Espacio)")
            self.recording_indicator.config(text="🔴 GRABANDO...", foreground="red")
            
        else:
            self.is_recording = False
            self.record_button.config(text="Grabar (Espacio)")
            self.recording_indicator.config(text="", foreground="black")
            
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
                
            if self.current_recording_data:
                csv_path = self.folder_path / f"{self.current_filename_base}.csv"
                pd.DataFrame(self.current_recording_data).to_csv(csv_path, index=False)
                
            sel = self.syllable_listbox.curselection()
            if sel:
                idx = sel[0]
                self.syllable_listbox.delete(idx)
                # Omitir el tick si es una repetición para que puedan seguir grabando la misma si lo desean
                # Pero si es la primera vez, marcamos como completado visualmente (aunque pueden repetirlo).
                self.syllable_listbox.insert(idx, f"[✓] {self.current_syllable}")
                self.syllable_listbox.itemconfig(idx, {'fg': 'green'})
                self.recorded_syllables.add(self.current_syllable)
                if idx < len(SYLLABLES) - 1:
                    self.syllable_listbox.selection_clear(0, tk.END)
                    self.syllable_listbox.selection_set(idx + 1)

    def update_camera(self):
        if not self.running: return

        ret, frame = self.cap.read()
        if ret:
            frame = cv2.flip(frame, 1) 
            if self.is_recording and self.video_writer:
                self.video_writer.write(frame)
                
            self.process_frame(frame)
            
            if self.is_capturing_neutral:
                self.process_neutral_calibration()

            img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
            img.thumbnail((640, 480))
            img_tk = ImageTk.PhotoImage(image=img)
            self.video_label.configure(image=img_tk)
            self.video_label.image = img_tk

        self.root.after(15, self.update_camera)

    def process_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb)

        if results.multi_face_landmarks:
            landmarks = results.multi_face_landmarks[0].landmark
            
            nx = landmarks[POINTS["NARIZ_REF"]].x * self.frame_width
            ny = landmarks[POINTS["NARIZ_REF"]].y * self.frame_height
            
            ex1 = landmarks[POINTS["OJO_IZQ"]].x * self.frame_width
            ey1 = landmarks[POINTS["OJO_IZQ"]].y * self.frame_height
            ex2 = landmarks[POINTS["OJO_DER"]].x * self.frame_width
            ey2 = landmarks[POINTS["OJO_DER"]].y * self.frame_height
            
            scale = math.hypot(ex2 - ex1, ey2 - ey1)
            if scale == 0: scale = 1 
            
            tilt_angle = math.atan2(ey2 - ey1, ex2 - ex1)
            
            cos_a = math.cos(tilt_angle)
            sin_a = math.sin(tilt_angle)
            
            # Aproximación de Yaw y Pitch
            z_ojo_izq = landmarks[POINTS["OJO_IZQ"]].z
            z_ojo_der = landmarks[POINTS["OJO_DER"]].z
            z_barbilla = landmarks[POINTS["BARBILLA"]].z
            z_frente = landmarks[10].z 
            
            # Usando asin con limite seguro
            yaw_aprox = math.asin(max(min(z_ojo_der - z_ojo_izq, 1.0), -1.0))
            pitch_aprox = math.asin(max(min(z_barbilla - z_frente, 1.0), -1.0))

            for pt in TRACKED_POINTS + ["NARIZ_REF", "OJO_IZQ", "OJO_DER"]:
                idx = POINTS[pt]
                cv2.circle(frame, (int(landmarks[idx].x * self.frame_width), int(landmarks[idx].y * self.frame_height)), 3, (0,255,0), -1)
            
            cv2.line(frame, (int(ex1), int(ey1)), (int(ex2), int(ey2)), (255, 0, 0), 2)

            for pt_name in TRACKED_POINTS:
                px = landmarks[POINTS[pt_name]].x * self.frame_width
                py = landmarks[POINTS[pt_name]].y * self.frame_height
                
                tx = px - nx
                ty = py - ny
                
                rx = tx * cos_a + ty * sin_a
                ry = -tx * sin_a + ty * cos_a
                
                self.current_normalized_points[pt_name] = {"x": rx / scale, "y": ry / scale}

            if self.is_recording and self.neutral_data:
                row = {
                    "Participante": self.participant_name,
                    "Silaba": self.current_syllable,
                    "Tiempo_ms": int((time.perf_counter() - self.start_time) * 1000),
                    "Escala_Px": scale,
                    "Inclinacion_Rad": tilt_angle,
                    "Yaw_Aprox_Rad": yaw_aprox,
                    "Pitch_Aprox_Rad": pitch_aprox
                }
                
                for pt in TRACKED_POINTS:
                    norm_x = self.current_normalized_points[pt]["x"]
                    norm_y = self.current_normalized_points[pt]["y"]
                    row[f"{pt}_Norm_X"] = norm_x
                    row[f"{pt}_Norm_Y"] = norm_y
                    row[f"{pt}_Delta_X"] = norm_x - self.neutral_data[pt]["x"]
                    row[f"{pt}_Delta_Y"] = norm_y - self.neutral_data[pt]["y"]
                    
                self.current_recording_data.append(row)
        else:
            # Manejo de frame sin detección
            if self.is_recording and self.neutral_data:
                 row = {
                     "Participante": self.participant_name,
                     "Silaba": self.current_syllable,
                     "Tiempo_ms": int((time.perf_counter() - self.start_time) * 1000),
                     "Escala_Px": float('nan'),
                     "Inclinacion_Rad": float('nan'),
                     "Yaw_Aprox_Rad": float('nan'),
                     "Pitch_Aprox_Rad": float('nan')
                 }
                 for pt in TRACKED_POINTS:
                     row[f"{pt}_Norm_X"] = float('nan')
                     row[f"{pt}_Norm_Y"] = float('nan')
                     row[f"{pt}_Delta_X"] = float('nan')
                     row[f"{pt}_Delta_Y"] = float('nan')
                 self.current_recording_data.append(row)


    def finish_session(self):
        if len(self.recorded_syllables) < len(SYLLABLES):
            if not messagebox.askyesno("Incompleto", "¿Finalizar sin terminar?"): return
        self.shutdown()

    def on_close(self):
        if self.is_recording:
            messagebox.showwarning("Grabando", "Detén la grabación antes de salir.")
            return
        self.shutdown()

    def shutdown(self):
        self.running = False
        if self.video_writer: self.video_writer.release()
        if self.cap.isOpened(): self.cap.release()
        self.face_mesh.close()
        cv2.destroyAllWindows()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = OrofacialApp(root)
    root.mainloop()
