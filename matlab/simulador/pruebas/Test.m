%% TEST_BARRIDO
% Barrido interactivo de la punta lingual.
%
% - Trayectoria definida mediante puntos [Y Z].
% - FEM geometrically no lineal.
% - Sin guiado impuesto al dorso o vientre.
% - Posturas FEM calculadas previamente.
% - Slider con interpolacion visual entre posturas.
% - Vistas sagital y tridimensional independientes.
%
% Las interpolaciones visuales NO son nuevas
% soluciones de equilibrio FEM.

clear; clc; close all;

%% =====================================================
% 1. MODELO DE REFERENCIA
% ======================================================

lengua0 = lengua_ideal(struct(),[],[]);

malla = crear_malla_lengua(lengua0);

opMaterial = struct();

opMaterial.E = 0.005;
opMaterial.nu = 0.40;
opMaterial.espesor = 1;

opMaterial.perfilRigidez = 'uniforme';
opMaterial.activarSoporteVentral = false;

opMaterial.factorAnclaje = 1.0;

% Nueva distribucion espacial.
opMaterial.modoAnclajePosterior = 'banda';

% Banda longitudinal de 5 mm.
opMaterial.anchoBandaPosterior = 5.0;

modelo = configurar_biomecanica( ...
    malla,opMaterial);

%% =====================================================
% 2. TRAYECTORIA DE LA PUNTA
% ======================================================

% Puntos aproximados del recorrido verde.
%
% [Y Z] en mm.
%
% Puedes modificar estos puntos para cambiar
% la trayectoria sin tocar el resto del script.

puntosRuta = [
     0.0    0.0
    -2.0    8.0
    -5.0   15.5
    -9.0   19.0
   -17.0   22.0
   -28.0   24.2
   -40.0   24.0
];

% Numero de soluciones FEM a calcular.
% Las posiciones intermedias del slider seran
% interpolaciones graficas de estas soluciones.

nMuestras = 17;

% Parametro de longitud de arco de la trayectoria.
segmentos = diff(puntosRuta,1,1);

longitudes = sqrt(sum(segmentos.^2,2));

sRuta = [0;cumsum(longitudes)];

sMuestras = linspace( ...
    0,sRuta(end),nMuestras)';

ruta = [
    interp1(sRuta,puntosRuta(:,1), ...
        sMuestras,'pchip'), ...
    interp1(sRuta,puntosRuta(:,2), ...
        sMuestras,'pchip')
];

%% =====================================================
% 3. SOLUCIONADOR FEM
% ======================================================

opFEM = struct();

opFEM.nPasos = 30;
opFEM.maxIter = 45;
opFEM.tolFuerza = 1e-9;
opFEM.maxBacktrack = 30;

% Umbral exploratorio para detener el barrido
% antes de aceptar configuraciones muy comprimidas.
% NO es un limite fisiologico validado.

Jcritico = 0.84;


%% MODO DE BARRIDO

% "libre"    : punta prescrita, resto en equilibrio libre
% "inferior" : cuerpo guiado para permanecer mas bajo

modoBarrido = "inferior";

%% OPCIONES PARA EL GUIADO INFERIOR

opB = struct();

opB.mostrarConsola = false;
opB.validar = true;

opB.factorRigidezGuia = 0.20;
opB.factorRigidezAngular = 0.20;

% Sin curvatura adicional prescrita.
opB.factorRigidezCurvatura = 0;
opB.factorRigidezAngularLamina = 0;

opB.distribucionGuia = struct( ...
    'modo','distribuido', ...
    'radio',0.08, ...
    'fraccionDistribuida',0.80, ...
    'excluirPunta',true);

opB.suavidad = struct( ...
    'activar',true, ...
    'factorDorsal',0.03, ...
    'factorVentral',0.03, ...
    'inicio',0.02, ...
    'fin',0.895, ...
    'anchoTransicion',0.04, ...
    'longitudReferencia',2.0);

opB.opcionesNoLineales = opFEM;

% El test ya tiene sus propias ventanas.
opB.visualizacion = struct();

opB.visualizacion.graficar = false;
opB.visualizacion.mostrarCavidad = false;
opB.visualizacion.mostrarBase = false;
opB.visualizacion.mostrarPuntos = false;
opB.visualizacion.mostrarReposo3D = false;


%% =====================================================
% 4. CALCULAR POSTURAS
% ======================================================

fprintf('\n===== BARRIDO LINGUAL =====\n');

fprintf('Modo: %s\n',modoBarrido);

fprintf('Puntos de trayectoria: %d\n', ...
    size(puntosRuta,1));

fprintf('Muestras FEM solicitadas: %d\n', ...
    nMuestras);

poses = cell(nMuestras,1);

nValidas = 0;

%% GEOMETRIA DE REFERENCIA PARA GUIADO

yPerfil0 = lengua0.sagital.y(:);

zDorsoPerfil0 = ...
    lengua0.sagital.zSuperior(:);

zVientrePerfil0 = ...
    lengua0.sagital.zInferior(:);

yPunta0 = lengua0.punta(2);
zPunta0 = lengua0.punta(3);

longitud = yPunta0-min(yPerfil0);

% Posiciones materiales a controlar.
sGuia = [
    0.04
    0.08
    0.14
    0.24
    0.38
    0.55
    0.75
    ];

yReferencia = yPunta0-longitud*sGuia;

zDorso0 = interp1( ...
    yPerfil0,zDorsoPerfil0, ...
    yReferencia,'pchip');

zVientre0 = interp1( ...
    yPerfil0,zVientrePerfil0, ...
    yReferencia,'pchip');

% Fraccion de elevacion transmitida.
fraccionDorso = [
    0.95
    0.82
    0.55
    0.22
    0.06
    0.00
    0.00
];

fraccionVientre = [
    0.84
    0.67
    0.42
    0.17
    0.04
    0.00
    0.00
];

pesoDorso = [
    0.65
    0.80
    0.85
    0.75
    0.55
    0.40
    0.35
];

pesoVientre = [
    0.50
    0.65
    0.70
    0.60
    0.45
    0.30
    0.25
];

%% CALCULO DEL BARRIDO

for k = 1:nMuestras

    puntaObjetivo = ruta(k,:);

    fprintf('\nPostura %d/%d\n',k,nMuestras);

    fprintf('Objetivo Y=%.3f Z=%.3f mm\n', ...
        puntaObjetivo(1),puntaObjetivo(2));

    try

        %% A. MODO LIBRE O REPOSO INICIAL

        if modoBarrido == "libre" || k == 1

            objetivo = struct();

            objetivo.puntaYZ = puntaObjetivo;
            objetivo.modo = 'prescrito';
            objetivo.componentes = [true true];


            % Opciones particulares de esta postura.
            opFEMactual = opFEM;

            % En el barrido libre, utilizar el equilibrio
            % anterior como condicion inicial.

            if modoBarrido == "libre" && k > 1

                opFEMactual.uInicial = ...
                    poses{k-1}.estado.u;

                fprintf('Continuacion desde postura %d\n',k-1);

            end


            %% CONTINUACION ADAPTATIVA DEL MODO LIBRE
            
            if k == 1
            
                % Primera postura desde reposo.
                estado = resolver_postura_no_lineal( ...
                    modelo,objetivo,opFEM);
            
            else
            
                % Estado FEM previamente aceptado.
                uActual = poses{k-1}.estado.u;
                puntaActual = poses{k-1}.punta(:)';
            
                % Cola de objetivos pendientes.
                pendientes = puntaObjetivo(:)';
            
                maxDivisiones = 12;
                divisiones = 0;
            
                distanciaMinima = 0.05; % mm
            
                while ~isempty(pendientes)
            
                    % Siguiente posicion a resolver.
                    candidato = pendientes(1,:);
            
                    pendientes(1,:) = [];
            
                    opcionesPaso = opFEM;
                    opcionesPaso.uInicial = uActual;
            
                    objetivoPaso = objetivo;
                    objetivoPaso.puntaYZ = candidato;
            
                    try
            
                        estadoPrueba = resolver_postura_no_lineal( ...
                            modelo,objetivoPaso,opcionesPaso);
            
                        % Comprobar integridad local.
                        Jprueba = estadoPrueba.diagnostico.Jmin;


                        %% MAPA DE COMPRESION EN POSTURA RECHAZADA

                        if isfinite(Jprueba) && Jprueba < Jcritico

                            X0 = modelo.malla.nodos;
                            X1 = estadoPrueba.nodos;
                            tri = modelo.malla.elementos;

                            a0 = X0(tri(:,1),:);
                            b0 = X0(tri(:,2),:);
                            c0 = X0(tri(:,3),:);

                            a1 = X1(tri(:,1),:);
                            b1 = X1(tri(:,2),:);
                            c1 = X1(tri(:,3),:);

                            A0 = (b0(:,1)-a0(:,1)).*(c0(:,2)-a0(:,2)) ...
                                - (b0(:,2)-a0(:,2)).*(c0(:,1)-a0(:,1));

                            A1 = (b1(:,1)-a1(:,1)).*(c1(:,2)-a1(:,2)) ...
                                - (b1(:,2)-a1(:,2)).*(c1(:,1)-a1(:,1));

                            J = A1./A0;

                            [Jordenado,indices] = sort(J);

                            fprintf('\n===== COMPRESION LOCAL =====\n');

                            for ii = 1:min(5,numel(J))

                                e = indices(ii);

                                centro = mean(X0(tri(e,:),:),1);

                                fprintf( ...
                                    'Elemento %d: J=%.5f, Y=%.2f, Z=%.2f\n', ...
                                    e,Jordenado(ii),centro(1),centro(2));

                            end

                            fprintf('Elementos con J < %.2f: %d/%d\n', ...
                                Jcritico,nnz(J<Jcritico),numel(J));

                            figure('Name','Compresion FEM - Postura rechazada', ...
                                'Color','w');

                            patch( ...
                                'Faces',tri, ...
                                'Vertices',X1, ...
                                'FaceVertexCData',J, ...
                                'FaceColor','flat', ...
                                'EdgeColor',[0.45 0.45 0.45], ...
                                'LineWidth',0.2);

                            colormap(turbo);
                            colorbar;
                            clim([0.70 1.10]);

                            axis equal;
                            grid on;

                            set(gca,'XDir','reverse');

                            xlabel('Y (mm)');
                            ylabel('Z (mm)');

                            title(sprintf( ...
                                'Distribucion local de J - minimo %.4f', ...
                                min(J)));

                        end
            
                        if ~isfinite(Jprueba) || Jprueba < Jcritico
            
                            error('Barrido:LimiteJ', ...
                                'Jmin %.6f inferior al limite %.4f.', ...
                                Jprueba,Jcritico);
            
                        end
            
                        % Aceptar el nuevo equilibrio.
                        estado = estadoPrueba;
            
                        uActual = estado.u;
                        puntaActual = estado.puntaYZ(:)';
            
                    catch ME
            
                        % No ocultar fallos ajenos a la
                        % convergencia numerica.
                        mensaje = string(ME.message);
            
                        falloNumerico = ...
                            contains(mensaje,'Newton no convergio') || ...
                            contains(mensaje,'Configuracion invertida') || ...
                            contains(mensaje, ...
                                'No se encontro un incremento valido');
            
                        if ~falloNumerico
                            rethrow(ME);
                        end
            
                        distancia = norm(candidato-puntaActual);
            
                        if divisiones >= maxDivisiones || ...
                                distancia < distanciaMinima
            
                            error('Barrido:ContinuacionFallida', ...
                                ['No se pudo avanzar hasta ', ...
                                 '[%.3f %.3f] mm. Ultimo punto ', ...
                                 '[%.3f %.3f] mm. Causa: %s'], ...
                                candidato(1),candidato(2), ...
                                puntaActual(1),puntaActual(2), ...
                                ME.message);
            
                        end
            
                        % Subdivision por punto medio.
                        intermedio = ...
                            0.5*(puntaActual+candidato);
            
                        % Resolver primero el intermedio y
                        % despues volver a intentar el destino.
                        pendientes = [
                            intermedio;
                            candidato;
                            pendientes
                        ];
            
                        divisiones = divisiones+1;
            
                        fprintf(['Subdivision %d: ', ...
                            'nuevo objetivo [%.3f %.3f]\n'], ...
                            divisiones, ...
                            intermedio(1),intermedio(2));
            
                    end
            
                end
            
                fprintf('Subdivisiones necesarias: %d\n', ...
                    divisiones);
            
            end
            
            %% RECONSTRUCCION
            
            [lenguaFinal,~] = reconstruir_lengua_3d( ...
                lengua0,malla,estado,[]);
        

        %% B. MODO INFERIOR GUIADO

        elseif modoBarrido == "inferior"

            % Elevacion total de la punta.
            h = max(0, ...
                puntaObjetivo(2)-zPunta0);

            % Objetivos distribuidos.
            zDorsoObjetivo = ...
                zDorso0+h*fraccionDorso;

            zVientreObjetivo = ...
                zVientre0+h*fraccionVientre;

            % Configurar postura.
            postura = struct();

            postura.puntaYZ = puntaObjetivo;

            postura.anguloApice = NaN;
            postura.anguloLamina = NaN;
            postura.pesoAngulo = 1.0;

            postura.curvaturaApical = 0;
            postura.curvaturaLaminal = 0;

            % Dorso [s Y Z Peso].
            postura.dorso = [
                sGuia, ...
                nan(size(sGuia)), ...
                zDorsoObjetivo, ...
                pesoDorso
            ];

            % Vientre [s Y Z Peso].
            postura.vientre = [
                sGuia, ...
                nan(size(sGuia)), ...
                zVientreObjetivo, ...
                pesoVientre
            ];


            % Opciones independientes para esta postura.
            opBactual = opB;

            % Utilizar la postura convergida anterior
            % como aproximacion inicial.
            if k > 1

                opBactual.opcionesNoLineales.uInicial = ...
                    poses{k-1}.estado.u;

                fprintf('Continuacion inferior desde postura %d\n',k-1);

            end

            % Resolver postura.
            simulacion = simular_postura_lingual( ...
                modelo,lengua0,postura,opBactual);


            estado = simulacion.estado;

            lenguaFinal = simulacion.lengua;

        else

            error('Modo de barrido desconocido.');

        end

        %% C. VALIDACION DE LA POSTURA

        Jmin = estado.diagnostico.Jmin;


        %% MOVILIDAD DEL EXTREMO POSTERIOR

        idsPosterior = modelo.malla.frontera.posterior(:);

        despPosterior = ...
            estado.desplazamientos(idsPosterior,:);

        movimientoMedio = mean(despPosterior,1);

        fprintf('Movimiento posterior medio:\n');

        fprintf('  dY = %+.4f mm\n', ...
            movimientoMedio(1));

        fprintf('  dZ = %+.4f mm\n', ...
            movimientoMedio(2));

        fprintf('  Magnitud = %.4f mm\n', ...
            norm(movimientoMedio));

        if ~isfinite(Jmin) || Jmin < Jcritico

            %% DIAGNOSTICO DEL ELEMENTO MAS COMPRIMIDO

            X0 = modelo.malla.nodos;
            X1 = estado.nodos;
            tri = modelo.malla.elementos;

            a0 = X0(tri(:,1),:);
            b0 = X0(tri(:,2),:);
            c0 = X0(tri(:,3),:);

            a1 = X1(tri(:,1),:);
            b1 = X1(tri(:,2),:);
            c1 = X1(tri(:,3),:);

            A0 = (b0(:,1)-a0(:,1)).*(c0(:,2)-a0(:,2)) ...
                - (b0(:,2)-a0(:,2)).*(c0(:,1)-a0(:,1));

            A1 = (b1(:,1)-a1(:,1)).*(c1(:,2)-a1(:,2)) ...
                - (b1(:,2)-a1(:,2)).*(c1(:,1)-a1(:,1));

            J = A1./A0;

            [JminLocal,e] = min(J);

            centro = mean(X0(tri(e,:),:),1);

            L = max(X0(:,1))-min(X0(:,1));

            s = (max(X0(:,1))-centro(1))/L;

            fprintf('\n===== REGION CRITICA =====\n');

            fprintf('Elemento: %d\n',e);
            fprintf('J minimo: %.6f\n',JminLocal);
            fprintf('Posicion material s: %.4f\n',s);
            fprintf('Centro YZ: [%.3f %.3f] mm\n',centro);

            if s < 0.12
                region = 'Apice';
            elseif s < 0.32
                region = 'Lamina';
            elseif s < 0.895
                region = 'Cuerpo';
            else
                region = 'Posterior';
            end

            fprintf('Region aproximada: %s\n',region);
            fprintf('Objetivo rechazado: [%.3f %.3f] mm\n', ...
                puntaObjetivo(1),puntaObjetivo(2));

            warning(['Barrido detenido: ', ...
                'Jmin=%.5f, limite=%.3f.'], ...
                Jmin,Jcritico);

            break

        end

        %% D. GUARDAR RESULTADO

        poses{k} = struct( ...
            'estado',estado, ...
            'lengua',lenguaFinal, ...
            'punta',estado.puntaYZ);

        nValidas = k;

        fprintf('Jmin = %.6f\n',Jmin);

        fprintf('Punta final = [%.3f %.3f]\n', ...
            estado.puntaYZ(1), ...
            estado.puntaYZ(2));

    catch ME

        warning( ...
            'Barrido detenido en postura %d: %s', ...
            k,ME.message);

        fprintf('\nDetalle del error:\n');

        fprintf('%s\n',getReport( ...
            ME,'extended','hyperlinks','off'));

        break

    end

end

%% RESULTADOS

poses = poses(1:nValidas);

fprintf('\n===== RESULTADO DEL BARRIDO =====\n');

fprintf('Modo utilizado: %s\n',modoBarrido);

fprintf('Posturas FEM validas: %d/%d\n', ...
    nValidas,nMuestras);

if nValidas > 0

    fprintf('Ultima punta alcanzada: [%.3f %.3f]\n', ...
        poses{end}.punta(1), ...
        poses{end}.punta(2));

end

if nValidas < 2

    error(['Se requieren al menos dos posturas ', ...
        'validas para construir el barrido.']);

end

rutaValida = ruta(1:nValidas,:);


%% =====================================================
% 5. FIGURA SAGITAL
% ======================================================

figSagital = figure( ...
    'Name','Barrido lingual - Sagital', ...
    'NumberTitle','off', ...
    'Color','w', ...
    'WindowStyle','normal', ...
    'Position',[80 120 1100 720]);

axSagital = axes( ...
    'Parent',figSagital, ...
    'Position',[0.09 0.23 0.86 0.69]);

hold(axSagital,'on');

S = poses{1}.lengua.sagital;

% Reposo.
plot(axSagital, ...
    lengua0.sagital.y, ...
    lengua0.sagital.zSuperior, ...
    'k--','LineWidth',1.2, ...
    'DisplayName','Reposo');

% Trayectoria solicitada.
plot(axSagital, ...
    ruta(:,1),ruta(:,2), ...
    '--','Color',[0.15 0.65 0.25], ...
    'LineWidth',1.5, ...
    'DisplayName','Ruta objetivo');

% Dorso deformado.
hDorso = plot(axSagital, ...
    S.ySuperior,S.zSuperior, ...
    'r-','LineWidth',2.2, ...
    'DisplayName','Dorso');

% Vientre deformado.
hVientre = plot(axSagital, ...
    S.yInferior,S.zInferior, ...
    'Color',[0.60 0.22 0.49], ...
    'LineWidth',1.9, ...
    'DisplayName','Vientre');

% Punta.
hPuntaSagital = plot(axSagital, ...
    poses{1}.punta(1), ...
    poses{1}.punta(2), ...
    'ro','MarkerSize',8, ...
    'MarkerFaceColor','r', ...
    'DisplayName','Punta');

set(axSagital,'XDir','reverse');

xlabel(axSagital,'Y (mm)');
ylabel(axSagital,'Z (mm)');

title(axSagital,'Barrido lingual - Plano sagital');

axis(axSagital,'equal');
grid(axSagital,'on');

xlim(axSagital,[-60 12]);
ylim(axSagital,[-12 35]);

legend(axSagital,'Location','best');

%% =====================================================
% 6. FIGURA TRIDIMENSIONAL
% ======================================================

fig3D = figure( ...
    'Name','Barrido lingual - Vista 3D', ...
    'NumberTitle','off', ...
    'Color','w', ...
    'WindowStyle','normal', ...
    'Position',[200 100 1100 730]);

ax3D = axes('Parent',fig3D);

hold(ax3D,'on');

L = poses{1}.lengua.malla;

hSuperficie = surf(ax3D, ...
    L.X,L.Y,L.Z, ...
    'FaceColor',[0.82 0.40 0.52], ...
    'EdgeColor','none', ...
    'FaceAlpha',0.98);

hPunta3D = plot3(ax3D, ...
    0,poses{1}.punta(1), ...
    poses{1}.punta(2), ...
    'ro','MarkerSize',8, ...
    'MarkerFaceColor','r');

% Trayectoria objetivo en el plano sagital X=0.
plot3(ax3D, ...
    zeros(nMuestras,1), ...
    ruta(:,1),ruta(:,2), ...
    '--','Color',[0.15 0.65 0.25], ...
    'LineWidth',1.3);

xlabel(ax3D,'X (mm)');
ylabel(ax3D,'Y (mm)');
zlabel(ax3D,'Z (mm)');

title(ax3D,'Barrido lingual - 3D');

axis(ax3D,'equal');
axis(ax3D,'vis3d');
grid(ax3D,'on');

xlim(ax3D,[-25 25]);
ylim(ax3D,[-60 12]);
zlim(ax3D,[-12 35]);

view(ax3D,[-60 25]);

camlight(ax3D,'headlight');
lighting(ax3D,'gouraud');

% La barra normal de MATLAB permite rotar,
% acercar, desplazar y activar Data Tips.

%% =====================================================
% 7. CONTROLES INTERACTIVOS
% ======================================================

controles = struct();

controles.hDorso = hDorso;
controles.hVientre = hVientre;

controles.hPuntaSagital = hPuntaSagital;
controles.hSuperficie = hSuperficie;
controles.hPunta3D = hPunta3D;

controles.axSagital = axSagital;
controles.ax3D = ax3D;

% Texto informativo.
controles.texto = uicontrol( ...
    'Parent',figSagital, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.10 0.035 0.75 0.04], ...
    'BackgroundColor','w', ...
    'FontSize',11, ...
    'HorizontalAlignment','left');

% Slider de posicion continua.
slider = uicontrol( ...
    'Parent',figSagital, ...
    'Style','slider', ...
    'Units','normalized', ...
    'Position',[0.10 0.11 0.68 0.045], ...
    'Min',1, ...
    'Max',nValidas, ...
    'Value',1, ...
    'SliderStep',[ ...
        1/(nValidas-1), ...
        min(1,3/(nValidas-1))]);

% Boton de reproduccion.
uicontrol( ...
    'Parent',figSagital, ...
    'Style','pushbutton', ...
    'Units','normalized', ...
    'Position',[0.81 0.10 0.13 0.06], ...
    'String','Reproducir', ...
    'FontSize',10, ...
    'Callback',@(~,~) reproducirBarrido( ...
        slider,poses,controles));

% Callback del slider.
slider.Callback = @(src,~) actualizarBarrido( ...
    src.Value,poses,controles);

% Primera postura.
actualizarBarrido(1,poses,controles);

fprintf('\nSLIDER INTERACTIVO LISTO.\n');

%% =====================================================
% FUNCIONES LOCALES SOLO PARA ESTA PRUEBA
% ======================================================

function actualizarBarrido(valor,poses,h)

n = numel(poses);

valor = max(1,min(n,valor));

% Dos posturas FEM adyacentes.
i = min(floor(valor),n-1);

a = valor-i;

A = poses{i};
B = poses{i+1};

%% 1. INTERPOLACION DE PERFILES SAGITALES

SA = A.lengua.sagital;
SB = B.lengua.sagital;

ySup = (1-a)*SA.ySuperior + ...
    a*SB.ySuperior;

zSup = (1-a)*SA.zSuperior + ...
    a*SB.zSuperior;

yInf = (1-a)*SA.yInferior + ...
    a*SB.yInferior;

zInf = (1-a)*SA.zInferior + ...
    a*SB.zInferior;

set(h.hDorso, ...
    'XData',ySup, ...
    'YData',zSup);

set(h.hVientre, ...
    'XData',yInf, ...
    'YData',zInf);

%% 2. INTERPOLACION DE SUPERFICIE 3D

LA = A.lengua.malla;
LB = B.lengua.malla;

X = (1-a)*LA.X+a*LB.X;
Y = (1-a)*LA.Y+a*LB.Y;
Z = (1-a)*LA.Z+a*LB.Z;

set(h.hSuperficie, ...
    'XData',X, ...
    'YData',Y, ...
    'ZData',Z);

%% 3. POSICION DE PUNTA

punta = (1-a)*A.punta+a*B.punta;

set(h.hPuntaSagital, ...
    'XData',punta(1), ...
    'YData',punta(2));

set(h.hPunta3D, ...
    'XData',0, ...
    'YData',punta(1), ...
    'ZData',punta(2));

%% 4. INFORMACION

if abs(a) < 1e-9 || abs(a-1) < 1e-9

    indice = round(valor);

    mensaje = sprintf( ...
        'FEM %d/%d  |  Y = %.2f mm  |  Z = %.2f mm  |  Jmin = %.4f', ...
        indice,n,punta(1),punta(2), ...
        poses{indice}.estado.diagnostico.Jmin);

else

    mensaje = sprintf( ...
        'Interpolacion visual %.2f/%d  |  Y = %.2f mm  |  Z = %.2f mm', ...
        valor,n,punta(1),punta(2));

end

set(h.texto,'String',mensaje);

drawnow limitrate;

end

function reproducirBarrido(slider,poses,h)

n = numel(poses);

% Cinco subintervalos graficos entre
% soluciones FEM consecutivas.

valores = [1:0.20:n,n];

for valor = valores

    if ~isgraphics(slider)
        break
    end

    slider.Value = valor;

    actualizarBarrido(valor,poses,h);

    drawnow;
    pause(0.035);

end

end
