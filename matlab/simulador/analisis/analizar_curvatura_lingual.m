
function analisis = analizar_curvatura_lingual( ...
    lengua0, lenguaNueva, regiones, opciones)
% ANALIZAR_CURVATURA_LINGUAL
% Analisis sagital de orientacion, flexion relativa
% y curvatura firmada del dorso lingual.
%
% ENTRADAS:
%   lengua0     : estructura de lengua_ideal
%   lenguaNueva : reconstruccion FEM-3D
%   regiones    : definir_regiones_funcionales
%   opciones    : opciones de calculo
%
% SALIDAS:
%   analisis.perfil
%   analisis.regiones
%   analisis.resumen
%   analisis.flexion
%   analisis.orientacionCuerpo
%   analisis.resumenFlexion
%   analisis.control
%
% Los angulos regionales se calculan mediante
% cuerdas interiores del dorso.
%
% La curvatura se estima mediante ajustes
% cuadraticos locales sobre el arco de referencia.
%
% Unidades: mm, grados y 1/mm.
% No modifica la geometria ni el FEM.

%% 1. OPCIONES

if nargin < 4 || isempty(opciones)
    opciones = struct();
end

if ~isstruct(opciones) || ~isscalar(opciones)
    error('opciones debe ser una estructura escalar.');
end

radio = leer(opciones,'radioAjuste',2.0);
margen = leer(opciones,'margenExtremos',1.0);
fraccionInterior = leer( ...
    opciones,'fraccionInterior',0.15);

validateattributes(radio,{'numeric'}, ...
    {'scalar','real','finite','positive'});

validateattributes(margen,{'numeric'}, ...
    {'scalar','real','finite','>=',0});

validateattributes(fraccionInterior,{'numeric'}, ...
    {'scalar','real','finite','>',0,'<',0.5});

%% 2. OBTENER PERFILES

if ~isfield(lengua0,'sagital') || ...
        ~isfield(lenguaNueva,'sagital')
    error('Estructuras linguales invalidas.');
end

y0 = lengua0.sagital.y(:);
z0 = lengua0.sagital.zSuperior(:);

y1 = lenguaNueva.sagital.ySuperior(:);
z1 = lenguaNueva.sagital.zSuperior(:);

n = numel(y0);

if n < 15 || numel(z0) ~= n || ...
        numel(y1) ~= n || numel(z1) ~= n
    error('Perfiles sagitales incompatibles.');
end

if any(~isfinite([y0;z0;y1;z1])) || ...
        any(diff(y0) <= 0)
    error('Coordenadas sagitales invalidas.');
end

%% 3. COORDENADAS MATERIALES

% El perfil esta ordenado desde posterior
% hacia la punta.

dt = hypot(diff(y0),diff(z0));
t = [0;cumsum(dt)];

if any(dt <= 0)
    error('Longitud de arco invalida.');
end

longitudY = y0(end)-y0(1);

if longitudY <= 0
    error('Longitud lingual invalida.');
end

% s=0 en punta, s=1 en extremo posterior.
s = (y0(end)-y0)/longitudY;

%% 4. CURVATURA Y ORIENTACION LOCAL

[k0,theta0] = derivadasLocales( ...
    y0,z0,t,radio);

[k1,theta1] = derivadasLocales( ...
    y1,z1,t,radio);

% Ambas curvaturas son firmadas.
deltaK = k1-k0;

% Excluir extremos de estadisticas regionales.
% La punta es un cierre geometrico singular.
validos = t >= margen & ...
    t <= t(end)-margen;

if nnz(validos) < 10
    error('No hay suficientes muestras interiores.');
end

%% 5. PESOS DE INTEGRACION EN ARCO

% Cuadratura nodal trapezoidal para evitar
% depender de la densidad de muestreo.

pesosArco = zeros(n,1);

pesosArco(1) = dt(1)/2;
pesosArco(end) = dt(end)/2;

pesosArco(2:end-1) = ...
    (dt(1:end-1)+dt(2:end))/2;

%% 6. PESOS FUNCIONALES

if ~isstruct(regiones) || ...
        ~isfield(regiones,'configuracion') || ...
        ~isfield(regiones,'nombres')
    error('Regiones funcionales invalidas.');
end

limites = regiones.configuracion.limites;
ancho = regiones.configuracion.anchoTransicion;

if numel(limites) ~= 3 || ...
        any(~isfinite(limites)) || ...
        any(diff(limites) <= 0) || ...
        limites(1) <= 0 || limites(3) >= 1 || ...
        ~isscalar(ancho) || ~isfinite(ancho) || ancho <= 0
    error('Limites regionales invalidos.');
end

q1 = suave((s-limites(1))/ancho+0.5);
q2 = suave((s-limites(2))/ancho+0.5);
q3 = suave((s-limites(3))/ancho+0.5);

W = [
    1-q1, ...
    q1-q2, ...
    q2-q3, ...
    q3
];

if max(abs(sum(W,2)-1)) > 1e-10
    error('Los pesos regionales no suman uno.');
end

%% 7. DESPLAZAMIENTOS DEL DORSO

uY = y1-y0;
uZ = z1-z0;

magnitud = hypot(uY,uZ);

%% 8. ORIENTACIONES REGIONALES

nRegiones = 3;

intervalos = [
    0,limites(1);
    limites(1),limites(2);
    limites(2),limites(3)
];

angulos0 = zeros(nRegiones,1);
angulos1 = zeros(nRegiones,1);
cambios = zeros(nRegiones,1);

curvatura0Media = zeros(nRegiones,1);
curvatura1Media = zeros(nRegiones,1);
cambioKMedia = zeros(nRegiones,1);
cambioKRMS = zeros(nRegiones,1);

desplazamientosMedios = zeros(nRegiones,1);

datos = repmat(struct( ...
    'nombre',"", ...
    'anguloReposo',0, ...
    'anguloFinal',0, ...
    'cambioAngulo',0, ...
    'curvaturaRMS',0, ...
    'desplazamientoMedio',0, ...
    'curvaturaFirmadaReposo',0, ...
    'curvaturaFirmadaFinal',0, ...
    'cambioCurvaturaFirmada',0), ...
    nRegiones,1);

for i = 1:nRegiones

    inicio = intervalos(i,1);
    fin = intervalos(i,2);

    % Puntos interiores de cada region.
    sAnterior = inicio + ...
        fraccionInterior*(fin-inicio);

    sPosterior = fin - ...
        fraccionInterior*(fin-inicio);

    % Cuerda de reposo.
    pA0 = puntoMaterial(s,y0,z0,sAnterior);
    pP0 = puntoMaterial(s,y0,z0,sPosterior);

    % Cuerda deformada.
    pA1 = puntoMaterial(s,y1,z1,sAnterior);
    pP1 = puntoMaterial(s,y1,z1,sPosterior);

    v0 = pA0-pP0;
    v1 = pA1-pP1;

    if norm(v0) < 1e-10 || norm(v1) < 1e-10
        error('Cuerda degenerada en region %d.',i);
    end

    % Orientacion posterior hacia anterior.
    angulos0(i) = atan2d(v0(2),v0(1));
    angulos1(i) = atan2d(v1(2),v1(1));

    cambios(i) = envolver180( ...
        angulos1(i)-angulos0(i));

    %% 9. CURVATURA REGIONAL

    % Ponderacion por region y longitud de arco
    % del perfil original.
    w = W(:,i).*double(validos).*pesosArco;

    sumaW = sum(w);

    if sumaW <= 0
        error('Region %d sin muestras validas.',i);
    end

    % Curvatura firmada media.
    curvatura0Media(i) = sum(w.*k0)/sumaW;
    curvatura1Media(i) = sum(w.*k1)/sumaW;

    % Cambio firmado.
    cambioKMedia(i) = ...
        curvatura1Media(i)-curvatura0Media(i);

    % Magnitud del cambio, sin signo.
    cambioKRMS(i) = sqrt( ...
        sum(w.*deltaK.^2)/sumaW);

    % Desplazamiento del dorso.
    desplazamientosMedios(i) = ...
        sum(w.*magnitud)/sumaW;

    %% 10. ALMACENAMIENTO REGIONAL

    datos(i).nombre = string(regiones.nombres(i));

    datos(i).anguloReposo = angulos0(i);
    datos(i).anguloFinal = angulos1(i);
    datos(i).cambioAngulo = cambios(i);

    datos(i).curvaturaRMS = cambioKRMS(i);

    datos(i).desplazamientoMedio = ...
        desplazamientosMedios(i);

    datos(i).curvaturaFirmadaReposo = ...
        curvatura0Media(i);

    datos(i).curvaturaFirmadaFinal = ...
        curvatura1Media(i);

    datos(i).cambioCurvaturaFirmada = ...
        cambioKMedia(i);

end

%% 11. FLEXIONES RELATIVAS

% Angulos entre cuerdas regionales.
%
% Positivo: giro antihorario relativo al
% recorrer el perfil de posterior a anterior.

phiAL0 = envolver180(angulos0(1)-angulos0(2));
phiAL1 = envolver180(angulos1(1)-angulos1(2));

phiLC0 = envolver180(angulos0(2)-angulos0(3));
phiLC1 = envolver180(angulos1(2)-angulos1(3));

deltaAL = envolver180(phiAL1-phiAL0);
deltaLC = envolver180(phiLC1-phiLC0);

% Orientacion del cuerpo independiente.
thetaC0 = angulos0(3);
thetaC1 = angulos1(3);
deltaC = cambios(3);

%% 12. ESTRUCTURA DE FLEXION

flexion = struct();

flexion.apiceLamina.reposo_deg = phiAL0;
flexion.apiceLamina.final_deg = phiAL1;
flexion.apiceLamina.cambio_deg = deltaAL;

flexion.laminaCuerpo.reposo_deg = phiLC0;
flexion.laminaCuerpo.final_deg = phiLC1;
flexion.laminaCuerpo.cambio_deg = deltaLC;

orientacionCuerpo.reposo_deg = thetaC0;
orientacionCuerpo.final_deg = thetaC1;
orientacionCuerpo.cambio_deg = deltaC;

%% 13. RESULTADOS DEL PERFIL

analisis.perfil.s = s;
analisis.perfil.longitudArcoReferencia = t;

analisis.perfil.yReposo = y0;
analisis.perfil.zReposo = z0;

analisis.perfil.yFinal = y1;
analisis.perfil.zFinal = z1;

% Campos originales conservados.
analisis.perfil.curvaturaReposo = k0;
analisis.perfil.curvaturaFinal = k1;
analisis.perfil.deltaCurvatura = deltaK;

analisis.perfil.anguloTangenteReposo = theta0;
analisis.perfil.anguloTangenteFinal = theta1;

analisis.perfil.desplazamientoY = uY;
analisis.perfil.desplazamientoZ = uZ;

analisis.perfil.magnitudDesplazamiento = magnitud;
analisis.perfil.muestrasValidas = validos;

% Nombres explicitos para curvatura con signo.
analisis.perfil.curvaturaFirmadaReposo = k0;
analisis.perfil.curvaturaFirmadaFinal = k1;
analisis.perfil.cambioCurvaturaFirmada = deltaK;

analisis.perfil.pesosFuncionales = W;
analisis.perfil.pesosArcoReferencia = pesosArco;

%% 14. RESULTADOS REGIONALES

analisis.regiones = datos;

analisis.resumen = table( ...
    string(regiones.nombres(1:3))', ...
    angulos0, ...
    angulos1, ...
    cambios, ...
    cambioKRMS, ...
    desplazamientosMedios, ...
    curvatura0Media, ...
    curvatura1Media, ...
    cambioKMedia, ...
    'VariableNames',{ ...
    'Region', ...
    'AnguloReposo_deg', ...
    'AnguloFinal_deg', ...
    'CambioAngular_deg', ...
    'CambioCurvaturaRMS_1mm', ...
    'DesplazamientoMedio_mm', ...
    'CurvaturaFirmadaReposo_1mm', ...
    'CurvaturaFirmadaFinal_1mm', ...
    'CambioCurvaturaFirmada_1mm'});

%% 15. NUEVA TABLA DE FLEXION

analisis.flexion = flexion;

analisis.orientacionCuerpo = orientacionCuerpo;

analisis.resumenFlexion = table( ...
    ["Apice-Lamina";"Lamina-Cuerpo"], ...
    [phiAL0;phiLC0], ...
    [phiAL1;phiLC1], ...
    [deltaAL;deltaLC], ...
    'VariableNames',{ ...
    'Relacion', ...
    'FlexionReposo_deg', ...
    'FlexionFinal_deg', ...
    'CambioFlexion_deg'});

%% 16. VARIABLES PARA CONTROL INVERSO

% Vector de cambios respecto al reposo geometrico.
%
% [Flexion AL, Flexion LC, Orientacion del cuerpo]
%
% Para el control inverso, despues se restara
% la respuesta de una postura sin activacion,
% manteniendo la misma posicion de punta.

analisis.control.vector = [
    deltaAL;
    deltaLC;
    deltaC
];

analisis.control.nombres = [
    "Flexion Apice-Lamina";
    "Flexion Lamina-Cuerpo";
    "Orientacion Cuerpo"
];

analisis.control.unidades = 'grados';

end

%% FUNCION LOCAL: DERIVADAS GEOMETRICAS

function [curvatura,angulo] = ...
    derivadasLocales(y,z,t,radio)

n = numel(t);

curvatura = zeros(n,1);
angulo = zeros(n,1);

for i = 1:n

    indices = find(abs(t-t(i)) <= radio);

    % Asegurar siete puntos de ajuste.
    if numel(indices) < 7

        [~,orden] = sort(abs(t-t(i)));
        indices = sort(orden(1:7));

    end

    tau = t(indices)-t(i);

    A = [
        ones(numel(tau),1), ...
        tau, ...
        tau.^2
    ];

    py = A\y(indices);
    pz = A\z(indices);

    dy = py(2);
    dz = pz(2);

    ddy = 2*py(3);
    ddz = 2*pz(3);

    velocidad2 = dy^2+dz^2;

    if ~isfinite(velocidad2) || velocidad2 < 1e-12
        error('Tangente degenerada en muestra %d.',i);
    end

    % Curvatura firmada: 1/mm.
    curvatura(i) = ...
        (dy*ddz-dz*ddy)/(velocidad2^1.5);

    angulo(i) = atan2d(dz,dy);

end

end

%% FUNCION LOCAL: PUNTO MATERIAL

function p = puntoMaterial(s,y,z,consulta)

% s original es decreciente.
sAsc = flipud(s);

p = [
    interp1(sAsc,flipud(y),consulta,'linear'), ...
    interp1(sAsc,flipud(z),consulta,'linear')
];

end

%% FUNCION LOCAL: ENVOLVER ANGULOS

function a = envolver180(a)

% Evita depender de Mapping Toolbox.
a = mod(a+180,360)-180;

end

%% FUNCION LOCAL: SMOOTHSTEP

function q = suave(x)

x = max(0,min(1,x));
q = x.^2.*(3-2*x);

end

%% FUNCION LOCAL: OPCIONES

function valor = leer(opciones,nombre,defecto)

if isfield(opciones,nombre)
    valor = opciones.(nombre);
else
    valor = defecto;
end

end
