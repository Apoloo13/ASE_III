# import cv2
# import math
# import re
# import pandas as pd
# import mediapipe as mp
# import tkinter as tk

# from tkinter import ttk, messagebox, simpledialog
# from pathlib import Path
# from PIL import Image, ImageTk


# CAMERA_INDEX = 1

# POINTS = {
#     "CR": 291,
#     "CL": 61,
#     "UC": 0,
#     "DC": 17,
#     "UR": 269,
#     "UL": 39,
#     "DR": 405,
#     "DL": 181,
#     "EL": 133,
#     "ER": 362,
#     "EC": 168
# }

# DISTANCE_PAIRS = [
#     ("CR", "ER"),
#     ("CL", "EL"),
#     ("UC", "EC"),
#     ("DC", "EC"),

#     ("UR", "ER"),
#     ("UR", "EC"),
#     ("UL", "EL"),
#     ("UL", "EC"),

#     ("DR", "ER"),
#     ("DR", "EC"),
#     ("DL", "EL"),
#     ("DL", "EC")
# ]

# POSES = [
#     ("SR", "Serio (Relajado)"),
#     ("AR", "Apertura redondeada"),
#     ("SM", "Sonrisa máxima sin abrir"),
#     ("ELS", "Elevación del labio superior"),
#     ("DI", "Depresión del inferior"),
#     ("BLI", "Beso lateral (Izquierda)"),
#     ("BLD", "Beso lateral (Derecha)")
# ]


# class OrofacialApp:

#     def __init__(self, root):
#         self.root = root
#         self.root.title("Registro Orofacial")
#         self.root.protocol("WM_DELETE_WINDOW", self.on_close)

#         self.cap = cv2.VideoCapture(CAMERA_INDEX)

#         if not self.cap.isOpened():
#             messagebox.showerror(
#                 "Error",
#                 f"No se pudo abrir la cámara {CAMERA_INDEX}."
#             )
#             self.root.destroy()
#             return

#         self.mp_face_mesh = mp.solutions.face_mesh

#         self.face_mesh = self.mp_face_mesh.FaceMesh(
#             static_image_mode=True,
#             max_num_faces=1,
#             refine_landmarks=True,
#             min_detection_confidence=0.5
#         )

#         self.current_frame = None
#         self.records = {}
#         self.running = True

#         self.build_interface()
#         self.update_camera()

#     def build_interface(self):
#         self.video_label = ttk.Label(self.root)
#         self.video_label.pack(padx=10, pady=10)

#         self.status_var = tk.StringVar(
#             value="Perfiles registrados: 0 / 7"
#         )

#         self.status_label = ttk.Label(
#             self.root,
#             textvariable=self.status_var
#         )
#         self.status_label.pack(pady=(0, 8))

#         button_frame = ttk.Frame(self.root)
#         button_frame.pack(pady=(0, 12))

#         self.capture_button = ttk.Button(
#             button_frame,
#             text="Capturar datos",
#             command=self.capture_frame
#         )
#         self.capture_button.grid(row=0, column=0, padx=5)

#         self.finish_button = ttk.Button(
#             button_frame,
#             text="Terminar sesión",
#             command=self.finish_session,
#             state="disabled"
#         )
#         self.finish_button.grid(row=0, column=1, padx=5)

#     def update_camera(self):
#         if not self.running:
#             return

#         ret, frame = self.cap.read()

#         if ret:
#             frame = cv2.flip(frame, 1)
#             self.current_frame = frame.copy()

#             display_frame = frame.copy()
#             display_frame = self.draw_alignment_guides(display_frame)

#             rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
#             image = Image.fromarray(rgb)
#             image.thumbnail((900, 650))

#             image_tk = ImageTk.PhotoImage(image=image)

#             self.video_label.configure(image=image_tk)
#             self.video_label.image = image_tk

#         self.root.after(15, self.update_camera)

#     def draw_alignment_guides(self, frame):
#         height, width = frame.shape[:2]

#         margin_x = int(width * 0.18)
#         margin_y = int(height * 0.06)

#         guide_left = margin_x
#         guide_top = margin_y
#         guide_right = width - margin_x
#         guide_bottom = height - margin_y

#         cv2.rectangle(
#             frame,
#             (guide_left, guide_top),
#             (guide_right, guide_bottom),
#             (0, 160, 110),
#             3
#         )

#         center_x = width // 2
#         center_y = height // 2
#         cross_size = 14

#         cv2.line(
#             frame,
#             (center_x - cross_size, center_y),
#             (center_x + cross_size, center_y),
#             (255, 255, 0),
#             2
#         )
#         cv2.line(
#             frame,
#             (center_x, center_y - cross_size),
#             (center_x, center_y + cross_size),
#             (255, 255, 0),
#             2
#         )

#         try:
#             _, face_box = self.detect_points(frame)

#             x1 = int(face_box["x_min"])
#             y1 = int(face_box["y_min"])
#             x2 = int(face_box["x_max"])
#             y2 = int(face_box["y_max"])

#             face_center_x = int(face_box["center_x"])
#             face_center_y = int(face_box["center_y"])

#             cv2.rectangle(
#                 frame,
#                 (x1, y1),
#                 (x2, y2),
#                 (0, 255, 255),
#                 3
#             )

#             cv2.circle(
#                 frame,
#                 (face_center_x, face_center_y),
#                 4,
#                 (0, 255, 255),
#                 -1
#             )

#         except ValueError:
#             pass

#         return frame

#     def capture_frame(self):
#         ret, frame = self.cap.read()

#         if not ret:
#             messagebox.showerror(
#                 "Error",
#                 "No se pudo capturar el frame."
#             )
#             return

#         frame = cv2.flip(frame, 1)

#         self.capture_button.config(state="disabled")
#         self.open_pose_menu(frame.copy())

#     def open_pose_menu(self, captured_frame):
#         window = tk.Toplevel(self.root)
#         window.title("Seleccionar perfil")
#         window.transient(self.root)
#         window.grab_set()

#         def close_window():
#             self.capture_button.config(state="normal")
#             window.destroy()

#         window.protocol("WM_DELETE_WINDOW", close_window)

#         ttk.Label(
#             window,
#             text="Seleccione el perfil correspondiente a esta captura:"
#         ).pack(padx=15, pady=(15, 10))

#         rgb = cv2.cvtColor(
#             captured_frame,
#             cv2.COLOR_BGR2RGB
#         )

#         preview = Image.fromarray(rgb)
#         preview.thumbnail((500, 350))

#         preview_tk = ImageTk.PhotoImage(preview)

#         preview_label = ttk.Label(
#             window,
#             image=preview_tk
#         )
#         preview_label.image = preview_tk
#         preview_label.pack(padx=10, pady=10)

#         first_capture = len(self.records) == 0

#         for code, name in POSES:
#             button_text = name

#             if code in self.records:
#                 button_text += "  ✓"

#             button = ttk.Button(
#                 window,
#                 text=button_text,
#                 command=lambda c=code: self.register_pose(
#                     c,
#                     captured_frame,
#                     window
#                 )
#             )

#             if first_capture and code != "SR":
#                 button.config(state="disabled")

#             button.pack(
#                 fill="x",
#                 padx=20,
#                 pady=3
#             )

#     def register_pose(self, pose_code, frame, window):
#         try:
#             coordinates, face_box = self.detect_points(frame)

#         except ValueError as error:
#             window.destroy()
#             self.capture_button.config(state="normal")

#             messagebox.showerror(
#                 "Detección facial",
#                 str(error)
#             )
#             return

#         distances = self.calculate_distances(coordinates)

#         record = {
#             "Perfil": pose_code,
#             "Rect_Width_px": face_box["width"],
#             "Rect_Height_px": face_box["height"],
#             "Rect_Area_px2": face_box["area"]
#         }

#         for point_name in POINTS:
#             x, y = coordinates[point_name]
#             record[f"{point_name}_X_px"] = x
#             record[f"{point_name}_Y_px"] = y

#         for distance_name, value in distances.items():
#             record[f"{distance_name}_px"] = value

#         self.records[pose_code] = record

#         window.destroy()
#         self.capture_button.config(state="normal")
#         self.update_status()

#     def detect_points(self, frame):
#         rgb = cv2.cvtColor(
#             frame,
#             cv2.COLOR_BGR2RGB
#         )

#         results = self.face_mesh.process(rgb)

#         if not results.multi_face_landmarks:
#             raise ValueError(
#                 "No se detectó correctamente una cara en la captura."
#             )

#         landmarks = results.multi_face_landmarks[0].landmark
#         height, width = frame.shape[:2]

#         coordinates = {}

#         for name, index in POINTS.items():
#             landmark = landmarks[index]
#             x = landmark.x * width
#             y = landmark.y * height
#             coordinates[name] = (x, y)

#         xs = [landmark.x * width for landmark in landmarks]
#         ys = [landmark.y * height for landmark in landmarks]

#         x_min = min(xs)
#         x_max = max(xs)
#         y_min = min(ys)
#         y_max = max(ys)

#         face_box = {
#             "x_min": x_min,
#             "x_max": x_max,
#             "y_min": y_min,
#             "y_max": y_max,
#             "width": x_max - x_min,
#             "height": y_max - y_min,
#             "area": (x_max - x_min) * (y_max - y_min),
#             "center_x": (x_min + x_max) / 2.0,
#             "center_y": (y_min + y_max) / 2.0
#         }

#         return coordinates, face_box

#     def calculate_distances(self, coordinates):
#         distances = {}

#         for point_a, point_b in DISTANCE_PAIRS:
#             x1, y1 = coordinates[point_a]
#             x2, y2 = coordinates[point_b]

#             distance = math.hypot(
#                 x2 - x1,
#                 y2 - y1
#             )

#             distances[f"D_{point_a}_{point_b}"] = distance

#         return distances

#     def update_status(self):
#         registered = []

#         for code, _ in POSES:
#             if code in self.records:
#                 registered.append(code)

#         text = (
#             f"Perfiles registrados: "
#             f"{len(registered)} / {len(POSES)}"
#         )

#         if registered:
#             text += "\n" + ", ".join(registered)

#         self.status_var.set(text)

#         if len(self.records) == len(POSES):
#             self.finish_button.config(state="normal")
#         else:
#             self.finish_button.config(state="disabled")

#     def finish_session(self):
#         if len(self.records) != len(POSES):
#             return

#         participant_name = simpledialog.askstring(
#             "Guardar sesión",
#             "Nombre para el archivo:"
#         )

#         if participant_name is None:
#             return

#         participant_name = participant_name.strip()

#         if not participant_name:
#             messagebox.showwarning(
#                 "Nombre inválido",
#                 "Ingrese un nombre válido."
#             )
#             return

#         participant_name = re.sub(
#             r'[<>:"/\\|?*]',
#             "",
#             participant_name
#         )

#         participant_name = participant_name.strip()
#         participant_name = participant_name.replace(" ", "_")

#         if not participant_name:
#             messagebox.showwarning(
#                 "Nombre inválido",
#                 "Ingrese un nombre válido."
#             )
#             return

#         folder = self.get_script_folder()
#         file_index = self.get_next_index(folder)

#         filename = f"{file_index:02d}_{participant_name}.xlsx"
#         filepath = folder / filename

#         ordered_records = []

#         for code, _ in POSES:
#             ordered_records.append(self.records[code])

#         dataframe = pd.DataFrame(ordered_records)

#         try:
#             dataframe.to_excel(
#                 filepath,
#                 index=False,
#                 sheet_name="Mediciones",
#                 engine="openpyxl"
#             )

#         except Exception as error:
#             messagebox.showerror(
#                 "Error al guardar",
#                 str(error)
#             )
#             return

#         messagebox.showinfo(
#             "Sesión finalizada",
#             f"Archivo guardado:\n{filename}"
#         )

#         self.shutdown()

#     def get_script_folder(self):
#         try:
#             return Path(__file__).resolve().parent
#         except NameError:
#             return Path.cwd()

#     def get_next_index(self, folder):
#         used_indices = set()

#         pattern = re.compile(
#             r"^(\d+)_.*\.xlsx$",
#             re.IGNORECASE
#         )

#         for file in folder.glob("*.xlsx"):
#             match = pattern.match(file.name)

#             if match:
#                 used_indices.add(int(match.group(1)))

#         index = 0

#         while index in used_indices:
#             index += 1

#         return index

#     def on_close(self):
#         if self.records:
#             answer = messagebox.askyesno(
#                 "Salir",
#                 "Los datos de esta sesión no se guardarán.\n"
#                 "¿Desea salir?"
#             )

#             if not answer:
#                 return

#         self.shutdown()

#     def shutdown(self):
#         self.running = False

#         if self.cap.isOpened():
#             self.cap.release()

#         self.face_mesh.close()
#         cv2.destroyAllWindows()
#         self.root.destroy()


# if __name__ == "__main__":
#     root = tk.Tk()
#     app = OrofacialApp(root)
#     root.mainloop()
import cv2
import math
import time
import pandas as pd
import mediapipe as mp
import tkinter as tk

from tkinter import ttk, messagebox, simpledialog
from pathlib import Path
from PIL import Image, ImageTk

CAMERA_INDEX = 0  # Cambia a 1 si usas cámara externa

# Puntos anatómicos para el análisis de trayectoria
POINTS = {
    "NARIZ_REF": 1,      # Origen (Punto de anclaje que no se mueve)
    "OJO_IZQ": 133,      # Referencia para escala (Distancia interpupilar)
    "OJO_DER": 362,      # Referencia para escala
    "BOCA_SUP": 0,       # Labio superior
    "BOCA_INF": 17,      # Labio inferior
    "BOCA_IZQ": 61,      # Comisura izquierda
    "BOCA_DER": 291      # Comisura derecha
}

SYLLABLES = [
    "TA", "TE", "TI", "TO", "TU",
    "SA", "SE", "SI", "SO", "SU",
    "RA", "RE", "RI", "RO", "RU"
]

class OrofacialApp:
    def __init__(self, root):
        self.root = root
        self.root.withdraw() # Ocultar ventana principal mientras pide el nombre

        # 1. Pedir nombre del participante
        self.participant_name = simpledialog.askstring(
            "Nuevo Participante", 
            "Ingrese el nombre o código del participante:"
        )
        
        if not self.participant_name or not self.participant_name.strip():
            messagebox.showerror("Error", "Se requiere un nombre para continuar.")
            self.root.destroy()
            return
            
        self.participant_name = self.participant_name.strip().replace(" ", "_")
        
        # Crear carpeta del participante
        # Crear carpeta del participante en la ruta exacta del script
        try:
            script_dir = Path(__file__).resolve().parent
        except NameError:
            script_dir = Path.cwd() # Respaldo por si se corre en un entorno interactivo
            
        self.folder_path = script_dir / self.participant_name
        self.folder_path.mkdir(exist_ok=True)

        self.root.deiconify() # Mostrar ventana
        self.root.title(f"Registro de Trayectorias - {self.participant_name}")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 2. Inicializar Cámara y Mediapipe
        self.cap = cv2.VideoCapture(CAMERA_INDEX)
        if not self.cap.isOpened():
            messagebox.showerror("Error", f"No se pudo abrir la cámara {CAMERA_INDEX}.")
            self.root.destroy()
            return

        # Obtener resolución de la cámara para el VideoWriter
        self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            static_image_mode=False, # False para tracking en video
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )

        # Variables de estado
        self.running = True
        self.is_recording = False
        self.current_syllable = None
        self.video_writer = None
        self.start_time = 0
        
        # Reemplazar self.trajectory_data = [] por:
        self.current_recording_data = [] # Solo guardará los datos de la sílaba actual # Lista para almacenar todas las filas del CSV
        self.recorded_syllables = set()

        self.build_interface()
        self.update_camera()
        
        # Atajo de teclado: Barra espaciadora para grabar
        self.root.bind('<space>', lambda e: self.toggle_recording())

    def build_interface(self):
        main_frame = ttk.Frame(self.root)
        main_frame.pack(padx=10, pady=10, fill="both", expand=True)

        # Panel izquierdo: Video
        video_frame = ttk.Frame(main_frame)
        video_frame.grid(row=0, column=0, padx=10)
        
        self.video_label = ttk.Label(video_frame)
        self.video_label.pack()

        self.recording_indicator = ttk.Label(video_frame, text="", font=("Arial", 14, "bold"))
        self.recording_indicator.pack(pady=5)

        # Panel derecho: Controles
        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=0, column=1, sticky="n", padx=10)

        ttk.Label(control_frame, text="Sílabas a grabar:", font=("Arial", 12, "bold")).pack(pady=(0, 5))

        # Lista de sílabas
        self.syllable_listbox = tk.Listbox(control_frame, height=15, font=("Arial", 12))
        self.syllable_listbox.pack(fill="x", pady=5)
        
        for syl in SYLLABLES:
            self.syllable_listbox.insert(tk.END, f"[ ] {syl}")
        self.syllable_listbox.selection_set(0) # Seleccionar la primera por defecto

        self.record_button = ttk.Button(
            control_frame, 
            text="Grabar", 
            command=self.toggle_recording,
            style="TButton"
        )
        self.record_button.pack(fill="x", pady=15, ipady=10)

        self.finish_button = ttk.Button(
            control_frame, 
            text="Finalizar y Guardar Datos", 
            command=self.finish_session
        )
        self.finish_button.pack(fill="x", pady=5)

    def toggle_recording(self):
        if not self.is_recording:
            # --- INICIAR GRABACIÓN ---
            selection = self.syllable_listbox.curselection()
            if not selection:
                messagebox.showwarning("Atención", "Selecciona una sílaba de la lista.")
                return
                
            index = selection[0]
            self.current_syllable = SYLLABLES[index]
            
            # Limpiar la lista de datos para que esté en blanco para esta nueva toma
            self.current_recording_data = [] 
            
            # Preparar VideoWriter
            video_path = str(self.folder_path / f"{self.current_syllable}.avi")
            fourcc = cv2.VideoWriter_fourcc(*'XVID')
            self.video_writer = cv2.VideoWriter(
                video_path, fourcc, 30.0, (self.frame_width, self.frame_height)
            )
            
            self.is_recording = True
            self.start_time = time.time()
            
            self.record_button.config(text=f"Detener {self.current_syllable} (Espacio)")
            self.recording_indicator.config(text="🔴 GRABANDO...", foreground="red")
            
        else:
            # --- DETENER GRABACIÓN ---
            self.is_recording = False
            self.record_button.config(text="Grabar (Espacio)")
            self.recording_indicator.config(text="", foreground="black")
            
            if self.video_writer:
                self.video_writer.release()
                self.video_writer = None
                
            # GUARDAR EL CSV DE ESTA SÍLABA INMEDIATAMENTE
            if self.current_recording_data:
                import pandas as pd
                df = pd.DataFrame(self.current_recording_data)
                csv_path = self.folder_path / f"{self.current_syllable}.csv"
                df.to_csv(csv_path, index=False)
                
            # Marcar como completada en la interfaz
            selection = self.syllable_listbox.curselection()
            if selection:
                index = selection[0]
                self.syllable_listbox.delete(index)
                self.syllable_listbox.insert(index, f"[✓] {self.current_syllable}")
                self.syllable_listbox.itemconfig(index, {'fg': 'green'})
                self.recorded_syllables.add(self.current_syllable)
                
                # Auto-seleccionar la siguiente
                if index < len(SYLLABLES) - 1:
                    self.syllable_listbox.selection_clear(0, tk.END)
                    self.syllable_listbox.selection_set(index + 1)

    def update_camera(self):
        if not self.running:
            return

        ret, frame = self.cap.read()
        if ret:
            frame = cv2.flip(frame, 1) # Efecto espejo
            
            # Si está grabando, guardar el frame en el video
            if self.is_recording and self.video_writer:
                self.video_writer.write(frame)
                
            # Procesar puntos y guardarlos
            self.process_frame(frame)

            # Mostrar en Tkinter
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image = Image.fromarray(rgb)
            image.thumbnail((640, 480))
            image_tk = ImageTk.PhotoImage(image=image)

            self.video_label.configure(image=image_tk)
            self.video_label.image = image_tk

        self.root.after(15, self.update_camera)

    def process_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.face_mesh.process(rgb)

        if results.multi_face_landmarks:
            landmarks = results.multi_face_landmarks[0].landmark
            
            # Extraer coordenadas base
            nx = landmarks[POINTS["NARIZ_REF"]].x * self.frame_width
            ny = landmarks[POINTS["NARIZ_REF"]].y * self.frame_height
            
            ex1 = landmarks[POINTS["OJO_IZQ"]].x * self.frame_width
            ey1 = landmarks[POINTS["OJO_IZQ"]].y * self.frame_height
            ex2 = landmarks[POINTS["OJO_DER"]].x * self.frame_width
            ey2 = landmarks[POINTS["OJO_DER"]].y * self.frame_height
            
            # Escala (Distancia Interpupilar)
            scale = math.hypot(ex2 - ex1, ey2 - ey1)
            if scale == 0: scale = 1 # Prevenir división por cero
            
            # Dibujar malla básica en pantalla
            for pt_name in ["BOCA_SUP", "BOCA_INF", "BOCA_IZQ", "BOCA_DER", "NARIZ_REF"]:
                idx = POINTS[pt_name]
                cx = int(landmarks[idx].x * self.frame_width)
                cy = int(landmarks[idx].y * self.frame_height)
                cv2.circle(frame, (cx, cy), 3, (0, 255, 0), -1)

            # Si estamos grabando, extraer y normalizar datos
            if self.is_recording:
                current_time_ms = int((time.time() - self.start_time) * 1000)
                
                row = {
                    "Participante": self.participant_name,
                    "Silaba": self.current_syllable,
                    "Tiempo_ms": current_time_ms,
                    "Escala_Px": scale
                }
                
                for pt_name in ["BOCA_SUP", "BOCA_INF", "BOCA_IZQ", "BOCA_DER"]:
                    idx = POINTS[pt_name]
                    px = landmarks[idx].x * self.frame_width
                    py = landmarks[idx].y * self.frame_height
                    
                    # NORMALIZACIÓN ESPACIAL: 
                    # 1. Restamos la nariz para centrar en (0,0)
                    # 2. Dividimos por la distancia entre ojos
                    norm_x = (px - nx) / scale
                    norm_y = (py - ny) / scale
                    
                    row[f"{pt_name}_Norm_X"] = norm_x
                    row[f"{pt_name}_Norm_Y"] = norm_y
                    
                self.current_recording_data.append(row)

    def finish_session(self):
        if len(self.recorded_syllables) < len(SYLLABLES):
            ans = messagebox.askyesno(
                "Incompleto", 
                f"Faltan sílabas por grabar. ¿Seguro que deseas finalizar?"
            )
            if not ans: return

        messagebox.showinfo(
            "Éxito", 
            f"Sesión finalizada.\n\nTodos los videos y archivos CSV individuales se guardaron en:\n{self.folder_path}"
        )
        
        self.shutdown()

    def on_close(self):
        if self.is_recording:
            messagebox.showwarning("Grabando", "Detén la grabación antes de salir.")
            return
        self.shutdown()

    def shutdown(self):
        self.running = False
        if self.is_recording and self.video_writer:
            self.video_writer.release()
        if self.cap.isOpened():
            self.cap.release()
        self.face_mesh.close()
        cv2.destroyAllWindows()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = OrofacialApp(root)
    root.mainloop()