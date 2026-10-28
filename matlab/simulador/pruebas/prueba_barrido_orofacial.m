
%% PRUEBA_BARRIDO_OROFACIAL
% Etapa 7 - Barrido interactivo.
%
% Ejecutar DESPUES de principal.m.
%
% - Reutiliza las dos figuras existentes.
% - Mantiene fija la cavidad oral.
% - Calcula posturas FEM independientes.
% - Interpola visualmente entre soluciones.
% - No realiza simulacion dinamica.
%
% No utilizar clear ni close all.

%% =====================================================
% 1. COMPROBAR SISTEMA
% ======================================================

if ~exist('sistema','var') || ...
        ~exist('simulacion','var') || ...
        ~exist('cfg','var')

    error('Primero ejecuta principal.m.');

end

g = simulacion.graficos;

if ~isgraphics(g.figuraSagital) || ...
        ~isgraphics(g.figura3D)

    error('Las figuras originales deben permanecer abiertas.');

end


%% =====================================================
% 2. DEFINIR TRANSICION ENTRE POSTURAS
% ======================================================

transicion = cfg.secuencias.transicionCompleta;

P0 = transicion.inicio;
P1 = transicion.fin;

nPosturas = transicion.nPosturas;

% Verificar correspondencia de objetivos.
assert(isequal(size(P0.dorso),size(P1.dorso)));
assert(isequal(size(P0.vientre),size(P1.vientre)));

assert(isequal(P0.dorso(:,1),P1.dorso(:,1)));
assert(isequal(P0.vientre(:,1),P1.vientre(:,1)));

% Construir posturas intermedias.
posturasRuta = repmat(P0,nPosturas,1);

for k = 1:nPosturas

    % Progreso temporal normalizado.
    t = (k-1)/(nPosturas-1);

    % Interpolacion quintica suave.
    % No representa dinamica muscular.
    a = 6*t^5-15*t^4+10*t^3;

    P = P0;

    % Punta.
    P.puntaYZ = ...
        (1-a)*P0.puntaYZ + ...
        a*P1.puntaYZ;

    % Dorso: desplazamientos y pesos.
    P.dorso(:,2:3) = ...
        (1-a)*P0.dorso(:,2:3) + ...
        a*P1.dorso(:,2:3);

    % Vientre: desplazamientos y pesos.
    P.vientre(:,2:3) = ...
        (1-a)*P0.vientre(:,2:3) + ...
        a*P1.vientre(:,2:3);

    % Curvatura apical.
    P.curvaturaApical = ...
        (1-a)*P0.curvaturaApical + ...
        a*P1.curvaturaApical;

    % Curvatura laminal.
    P.curvaturaLaminal = ...
        (1-a)*P0.curvaturaLaminal + ...
        a*P1.curvaturaLaminal;

    % Angulos libres en esta prueba.
    P.anguloApice = NaN;
    P.anguloLamina = NaN;

    P.nombre = sprintf("Transicion %d",k);

    posturasRuta(k) = P;

end

%% =====================================================
% 3. OPCIONES DE SIMULACION
% ======================================================

opPrueba = cfg.simulacion;
opPrueba.visualizacion.graficar = false;

opPrueba.mostrarConsola = false;
opPrueba.validar = true;
opPrueba.calcularBaseComparativa = false;

poses = cell(nPosturas,1);

fprintf('\n===== BARRIDO OROFACIAL =====\n');

%% =====================================================
% 4. PRECALCULAR POSTURAS FEM
% ======================================================

for k = 1:nPosturas

    fprintf('\nCalculando postura %d/%d\n', ...
        k,nPosturas);

    posturaB = posturasRuta(k);

    % Resolver FEM.
    s = simular_postura_lingual( ...
        sistema.modeloFEM, ...
        sistema.lengua0, ...
        posturaB,opPrueba);

    % Analizar relacion con cavidad.
    a = analizar_articulacion(sistema,s);

    poses{k} = struct( ...
        'simulacion',s, ...
        'analisis',a);

    fprintf('Punta = [%.2f %.2f] mm\n', ...
        s.estado.puntaYZ);

    fprintf('Jmin = %.5f\n', ...
        s.estado.diagnostico.Jmin);

end

fprintf('\nPosturas FEM calculadas: %d\n',nPosturas);

%% =====================================================
% 5. PREPARAR CONTROLES
% ======================================================

fig = g.figuraSagital;

% Retirar controles de una ejecucion anterior.
delete(findall(fig,'Tag','sliderBarridoOrofacial'));
delete(findall(fig,'Tag','botonBarridoOrofacial'));
delete(findall(fig,'Tag','textoBarridoOrofacial'));

% Reservar espacio inferior para los controles.
set(g.axSagital, ...
    'Position',[0.10 0.24 0.85 0.68]);

slider = uicontrol( ...
    'Parent',fig, ...
    'Style','slider', ...
    'Tag','sliderBarridoOrofacial', ...
    'Units','normalized', ...
    'Position',[0.10 0.12 0.67 0.045], ...
    'Min',1, ...
    'Max',nPosturas, ...
    'Value',1, ...
    'SliderStep',[0.02 0.20]);

boton = uicontrol( ...
    'Parent',fig, ...
    'Style','pushbutton', ...
    'Tag','botonBarridoOrofacial', ...
    'Units','normalized', ...
    'Position',[0.80 0.10 0.14 0.07], ...
    'String','Reproducir', ...
    'FontSize',11);

texto = uicontrol( ...
    'Parent',fig, ...
    'Style','text', ...
    'Tag','textoBarridoOrofacial', ...
    'Units','normalized', ...
    'Position',[0.10 0.035 0.84 0.04], ...
    'BackgroundColor','w', ...
    'FontSize',10, ...
    'HorizontalAlignment','left');

%% =====================================================
% 6. GUARDAR DATOS DEL BARRIDO
% ======================================================

datos = struct();

datos.sistema = sistema;
datos.poses = poses;
datos.graficos = g;

datos.slider = slider;
datos.texto = texto;

datos.secuencias = cfg.secuencias;

setappdata(fig,'barridoOrofacial',datos);

%% =====================================================
% 7. ASIGNAR CALLBACKS
% ======================================================

slider.Callback = @(~,~) ...
    actualizarBarridoLocal(fig);

boton.Callback = @(~,~) ...
    reproducirBarridoLocal(fig);

%% =====================================================
% 8. MOSTRAR PRIMERA POSTURA
% ======================================================

actualizarBarridoLocal(fig);

fprintf('\nBARRIDO INTERACTIVO LISTO.\n');


%% =====================================================
% FUNCION LOCAL: ACTUALIZAR SLIDER
% ======================================================

function actualizarBarridoLocal(fig)

if ~isgraphics(fig)
    return
end

d = getappdata(fig,'barridoOrofacial');

n = numel(d.poses);

valor = max(1,min(n,d.slider.Value));

%% A. POSTURA FEM EXACTA

if abs(valor-round(valor)) < 1e-5

    k = round(valor);

    sim = d.poses{k}.simulacion;
    ana = d.poses{k}.analisis;

    p = sim.estado.puntaYZ;
    Jmin = sim.estado.diagnostico.Jmin;

    mensaje = sprintf( ...
        'FEM %d/%d | Y=%.2f | Z=%.2f mm | Jmin=%.4f', ...
        k,n,p(1),p(2),Jmin);

%% B. INTERPOLACION VISUAL

else

    i = floor(valor);
    j = min(i+1,n);

    a = valor-i;

    A = d.poses{i}.simulacion;
    B = d.poses{j}.simulacion;

    % Copiar estructura compatible.
    sim = A;

    %% SUPERFICIE 3D

    sim.lengua.malla.X = ...
        (1-a)*A.lengua.malla.X + ...
        a*B.lengua.malla.X;

    sim.lengua.malla.Y = ...
        (1-a)*A.lengua.malla.Y + ...
        a*B.lengua.malla.Y;

    sim.lengua.malla.Z = ...
        (1-a)*A.lengua.malla.Z + ...
        a*B.lengua.malla.Z;

    %% PERFIL SAGITAL

    campos = { ...
        'ySuperior', ...
        'zSuperior', ...
        'yInferior', ...
        'zInferior'};

    for c = 1:numel(campos)

        nombre = campos{c};

        sim.lengua.sagital.(nombre) = ...
            (1-a)*A.lengua.sagital.(nombre) + ...
            a*B.lengua.sagital.(nombre);

    end

    %% PUNTA Y COSTILLAS

    sim.estado.puntaYZ = ...
        (1-a)*A.estado.puntaYZ + ...
        a*B.estado.puntaYZ;

    sim.estado.costillasYZ = ...
        (1-a)*A.estado.costillasYZ + ...
        a*B.estado.costillasYZ;

    %% OBJETIVOS MATERIALES

    if isfield(A.resultado,'puntosFinal') && ...
            isfield(B.resultado,'puntosFinal') && ...
            isequal(size(A.resultado.puntosFinal), ...
                    size(B.resultado.puntosFinal))

        sim.resultado.puntosFinal = ...
            (1-a)*A.resultado.puntosFinal + ...
            a*B.resultado.puntosFinal;

    else

        sim.resultado.puntosFinal = zeros(0,2);

    end

    % No hay nuevo equilibrio FEM ni analisis
    % de contacto para la geometria interpolada.
    ana = [];

    p = sim.estado.puntaYZ;

    mensaje = sprintf( ...
        'Interpolacion visual %.2f/%d | Y=%.2f | Z=%.2f mm', ...
        valor,n,p(1),p(2));

end

%% C. ACTUALIZAR FIGURAS EXISTENTES

d.graficos = actualizar_visualizacion( ...
    d.graficos,d.sistema,sim,ana);

set(d.texto,'String',mensaje);

setappdata(fig,'barridoOrofacial',d);

drawnow limitrate;

end


%% =====================================================
% FUNCION LOCAL: REPRODUCCION
% ======================================================

function reproducirBarridoLocal(fig)

if ~isgraphics(fig)
    return
end

d = getappdata(fig,'barridoOrofacial');

n = numel(d.poses);

% Reproduccion visual con 12 pasos por intervalo.
nVisual = d.secuencias.pasosVisuales;
valores = linspace(1,n,nVisual*(n-1)+1);

for valor = valores

    if ~isgraphics(fig)
        break
    end

    d = getappdata(fig,'barridoOrofacial');

    if ~isgraphics(d.slider)
        break
    end

    d.slider.Value = valor;

    actualizarBarridoLocal(fig);

    drawnow;
    pause(d.secuencias.pausaVisual_s);

end

end
