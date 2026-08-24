// ============================================================
// TENTÁCULO X/Y - ESP32
//
// Joystick X -> GPIO 4
// Joystick Y -> GPIO 15
//
// Servo X -> GPIO 18
// Servo Y -> GPIO 19
//
// Joystick alimentado con 3.3 V
// ============================================================


// ============================================================
// PINES
// ============================================================

const int JOYSTICK_X = 4;
const int JOYSTICK_Y = 15;

const int SERVO_X = 18;
const int SERVO_Y = 19;


// ============================================================
// SERVO PWM
// ============================================================

const int FRECUENCIA_SERVO = 50;
const int RESOLUCION_PWM = 16;

const int PULSO_MIN = 500;
const int PULSO_MAX = 2400;


// ============================================================
// RECORRIDO DE LOS SERVOS
// ============================================================

const float X_MIN = 30;
const float X_CENTRO = 90;
const float X_MAX = 150;

const float Y_MIN = 30;
const float Y_CENTRO = 90;
const float Y_MAX = 150;


// ============================================================
// CALIBRACIÓN DEL JOYSTICK
// ============================================================

int centroX = 2048;
int centroY = 2048;

int minimoX = 0;
int maximoX = 4095;

int minimoY = 0;
int maximoY = 4095;


// ============================================================
// ZONA MUERTA
// ============================================================

const int ZONA_MUERTA = 120;


// ============================================================
// SUAVIZADO
// ============================================================

float posicionX = 90;
float posicionY = 90;

const float SUAVIZADO = 0.15;


// ============================================================
// INVERTIR EJES
// ============================================================

const bool INVERTIR_X = false;
const bool INVERTIR_Y = false;


// ============================================================
// PWM SERVO
// ============================================================

uint32_t anguloAPWM(float angulo)
{
  angulo = constrain(angulo, 0, 180);

  float pulso =
    PULSO_MIN +
    (angulo / 180.0) *
    (PULSO_MAX - PULSO_MIN);

  return (uint32_t)(
    (pulso / 20000.0) * 65535.0
  );
}


void moverServo(int pin, float angulo)
{
  ledcWrite(pin, anguloAPWM(angulo));
}


// ============================================================
// LECTURA FILTRADA DEL ADC
// ============================================================

int leerJoystick(int pin)
{
  // Descartar primera lectura
  analogRead(pin);

  delayMicroseconds(100);

  long suma = 0;

  const int muestras = 8;

  for (int i = 0; i < muestras; i++)
  {
    suma += analogRead(pin);
    delayMicroseconds(80);
  }

  return suma / muestras;
}


// ============================================================
// CALIBRAR CENTRO
// ============================================================

void calibrarCentro()
{
  Serial.println();
  Serial.println("============================");
  Serial.println(" CALIBRANDO CENTRO");
  Serial.println(" NO MUEVAS EL JOYSTICK");
  Serial.println("============================");

  long sumaX = 0;
  long sumaY = 0;

  const int muestras = 150;

  for (int i = 0; i < muestras; i++)
  {
    sumaX += leerJoystick(JOYSTICK_X);
    sumaY += leerJoystick(JOYSTICK_Y);

    delay(5);
  }

  centroX = sumaX / muestras;
  centroY = sumaY / muestras;

  Serial.print("Centro X = ");
  Serial.println(centroX);

  Serial.print("Centro Y = ");
  Serial.println(centroY);
}


// ============================================================
// CALIBRAR EXTREMOS
// ============================================================

void calibrarExtremos()
{
  Serial.println();
  Serial.println("============================");
  Serial.println(" CALIBRANDO EXTREMOS");
  Serial.println();
  Serial.println("MUEVE EL JOYSTICK");
  Serial.println("COMPLETAMENTE EN TODAS");
  Serial.println("LAS DIRECCIONES");
  Serial.println("============================");


  // Empezamos desde el centro

  minimoX = centroX;
  maximoX = centroX;

  minimoY = centroY;
  maximoY = centroY;


  // 5 segundos para mover el joystick

  unsigned long inicio = millis();

  while (millis() - inicio < 5000)
  {
    int x = leerJoystick(JOYSTICK_X);
    int y = leerJoystick(JOYSTICK_Y);


    if (x < minimoX)
      minimoX = x;

    if (x > maximoX)
      maximoX = x;


    if (y < minimoY)
      minimoY = y;

    if (y > maximoY)
      maximoY = y;


    Serial.print("X: ");
    Serial.print(x);

    Serial.print("   Y: ");
    Serial.println(y);
  }


  Serial.println();
  Serial.println("============================");
  Serial.println(" CALIBRACIÓN TERMINADA");
  Serial.println("============================");

  Serial.print("X MIN = ");
  Serial.println(minimoX);

  Serial.print("X CENTRO = ");
  Serial.println(centroX);

  Serial.print("X MAX = ");
  Serial.println(maximoX);

  Serial.println();

  Serial.print("Y MIN = ");
  Serial.println(minimoY);

  Serial.print("Y CENTRO = ");
  Serial.println(centroY);

  Serial.print("Y MAX = ");
  Serial.println(maximoY);

  Serial.println("============================");
}


// ============================================================
// CONVERTIR JOYSTICK A ÁNGULO
// ============================================================

float calcularAngulo(
  int lectura,
  int minimo,
  int centro,
  int maximo,
  float anguloMin,
  float anguloCentro,
  float anguloMax
)
{

  // ========================================================
  // ZONA MUERTA
  // ========================================================

  if (abs(lectura - centro) <= ZONA_MUERTA)
  {
    return anguloCentro;
  }


  // ========================================================
  // LADO NEGATIVO
  // izquierda / abajo
  // ========================================================

  if (lectura < centro)
  {
    float porcentaje =
      (float)(lectura - minimo) /
      (float)(centro - minimo);

    porcentaje =
      constrain(
        porcentaje,
        0.0,
        1.0
      );

    return
      anguloMin +
      porcentaje *
      (anguloCentro - anguloMin);
  }


  // ========================================================
  // LADO POSITIVO
  // derecha / arriba
  // ========================================================

  float porcentaje =
    (float)(lectura - centro) /
    (float)(maximo - centro);

  porcentaje =
    constrain(
      porcentaje,
      0.0,
      1.0
    );

  return
    anguloCentro +
    porcentaje *
    (anguloMax - anguloCentro);
}


// ============================================================
// SETUP
// ============================================================

void setup()
{
  Serial.begin(115200);

  analogReadResolution(12);

  analogSetPinAttenuation(
    JOYSTICK_X,
    ADC_11db
  );

  analogSetPinAttenuation(
    JOYSTICK_Y,
    ADC_11db
  );


  // Servo X

  ledcAttach(
    SERVO_X,
    FRECUENCIA_SERVO,
    RESOLUCION_PWM
  );


  // Servo Y

  ledcAttach(
    SERVO_Y,
    FRECUENCIA_SERVO,
    RESOLUCION_PWM
  );


  // Centrar servos

  moverServo(
    SERVO_X,
    X_CENTRO
  );

  moverServo(
    SERVO_Y,
    Y_CENTRO
  );


  delay(1000);


  // ========================================================
  // CALIBRACIÓN
  // ========================================================

  calibrarCentro();

  delay(1000);

  calibrarExtremos();


  posicionX = X_CENTRO;
  posicionY = Y_CENTRO;

  delay(500);
}


// ============================================================
// LOOP
// ============================================================

void loop()
{

  int valorX =
    leerJoystick(JOYSTICK_X);

  int valorY =
    leerJoystick(JOYSTICK_Y);


  // ========================================================
  // CALCULAR POSICIÓN X
  // ========================================================

  float objetivoX =
    calcularAngulo(
      valorX,
      minimoX,
      centroX,
      maximoX,
      X_MIN,
      X_CENTRO,
      X_MAX
    );


  // ========================================================
  // CALCULAR POSICIÓN Y
  // ========================================================

  float objetivoY =
    calcularAngulo(
      valorY,
      minimoY,
      centroY,
      maximoY,
      Y_MIN,
      Y_CENTRO,
      Y_MAX
    );


  // ========================================================
  // INVERTIR EJES
  // ========================================================

  if (INVERTIR_X)
  {
    objetivoX =
      X_CENTRO -
      (objetivoX - X_CENTRO);
  }


  if (INVERTIR_Y)
  {
    objetivoY =
      Y_CENTRO -
      (objetivoY - Y_CENTRO);
  }


  // ========================================================
  // SUAVIZADO
  // ========================================================

  posicionX +=
    (objetivoX - posicionX) *
    SUAVIZADO;

  posicionY +=
    (objetivoY - posicionY) *
    SUAVIZADO;


  // ========================================================
  // MOVER SERVOS
  // ========================================================

  moverServo(
    SERVO_X,
    posicionX
  );

  moverServo(
    SERVO_Y,
    posicionY
  );


  // ========================================================
  // MONITOR SERIAL
  // ========================================================

  Serial.print("X ADC: ");
  Serial.print(valorX);

  Serial.print(" -> ");
  Serial.print(posicionX, 1);

  Serial.print("°");

  Serial.print("     |     ");

  Serial.print("Y ADC: ");
  Serial.print(valorY);

  Serial.print(" -> ");
  Serial.print(posicionY, 1);

  Serial.println("°");


  delay(10);
}