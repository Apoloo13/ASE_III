
function interfaz = visualizar_trayectoria_fonema_s(tray)
% Reproduce estados FEM de /s/ sin recalcular el solver.
% Incluye slider, trayectorias materiales y GIF 2D/3D.

sistema = tray.sistema;
cfg = tray.cfg;

n = numel(tray.u);
np = numel(tray.nombres);

% Recorrido completo, reutilizando las soluciones FEM.
indicesCiclo = [1:n, n-1:-1:1];
nCiclo = numel(indicesCiclo);

%% 1. FIGURAS PRINCIPALES

g = visualizar_sistema_orofacial( ...
    sistema, ...
    tray.simulaciones{1}, ...
    tray.analisis{1}, ...
    cfg.visualizacion);

set(g.figuraSagital, ...
    'Name','/s/ - Trayectoria sagital');

set(g.figura3D, ...
    'Name','/s/ - Trayectoria tridimensional');

%% 2. FIJAR LIMITES PARA EVITAR SALTOS DE CAMARA

Sfinal = tray.simulaciones{end}.lengua.sagital;
Lfinal = tray.simulaciones{end}.lengua.malla;

x3 = [xlim(g.ax3D),min(Lfinal.X(:)),max(Lfinal.X(:))];
y3 = [ylim(g.ax3D),min(Lfinal.Y(:)),max(Lfinal.Y(:))];
z3 = [zlim(g.ax3D),min(Lfinal.Z(:)),max(Lfinal.Z(:))];

xlim(g.ax3D,[min(x3) max(x3)]);
ylim(g.ax3D,[min(y3) max(y3)]);
zlim(g.ax3D,[min(z3) max(z3)]);

x2 = [xlim(g.axSagital),Sfinal.ySuperior(:)', ...
      Sfinal.yInferior(:)'];

z2 = [ylim(g.axSagital),Sfinal.zSuperior(:)', ...
      Sfinal.zInferior(:)'];

xlim(g.axSagital,[min(x2) max(x2)]);
ylim(g.axSagital,[min(z2) max(z2)]);

set(g.ax3D, ...
    'XLimMode','manual', ...
    'YLimMode','manual', ...
    'ZLimMode','manual');

set(g.axSagital, ...
    'XLimMode','manual', ...
    'YLimMode','manual');

%% 3. CONTROLES SAGITALES

set(g.axSagital, ...
    'Units','normalized', ...
    'Position',[0.08 0.24 0.85 0.69]);

slider = uicontrol( ...
    'Parent',g.figuraSagital, ...
    'Style','slider', ...
    'Units','normalized', ...
    'Position',[0.09 0.145 0.66 0.045], ...
    'Min',1, ...
    'Max',nCiclo, ...
    'Value',1, ...
    'SliderStep',[1/(nCiclo-1),min(10/(nCiclo-1),1)]);

btnPlay = uicontrol( ...
    'Parent',g.figuraSagital, ...
    'Style','pushbutton', ...
    'Units','normalized', ...
    'Position',[0.77 0.125 0.18 0.080], ...
    'String','Reproducir', ...
    'FontSize',11);


btnGIF2D = uicontrol( ...
    'Parent',g.figuraSagital, ...
    'Style','pushbutton', ...
    'Units','normalized', ...
    'Position',[0.77 0.045 0.18 0.067], ...
    'String','Exportar GIF 2D');

%% MODO DE REPRODUCCION Y EXPORTACION

uicontrol( ...
    'Parent',g.figuraSagital, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.09 0.107 0.14 0.028], ...
    'String','Movimiento:', ...
    'HorizontalAlignment','left', ...
    'BackgroundColor','w', ...
    'FontSize',10);

modoRecorrido = uicontrol( ...
    'Parent',g.figuraSagital, ...
    'Style','popupmenu', ...
    'Units','normalized', ...
    'Position',[0.23 0.100 0.31 0.041], ...
    'String',{'Ida y regreso','Solo ida'}, ...
    'Value',1, ...
    'FontSize',10);

estadoTexto = uicontrol( ...
    'Parent',g.figuraSagital, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.09 0.045 0.66 0.060], ...
    'String','', ...
    'HorizontalAlignment','left', ...
    'BackgroundColor','w', ...
    'FontSize',10);

%% 4. CONTROLES DE ORIENTACION 3D

set(g.ax3D, ...
    'Units','normalized', ...
    'Position',[0.06 0.12 0.66 0.80]);

panel = uipanel( ...
    'Parent',g.figura3D, ...
    'Units','normalized', ...
    'Position',[0.755 0.105 0.225 0.80], ...
    'Title','Orientacion de camara', ...
    'FontSize',11);

crearBoton('Isometrica',0.85,0, ...
    @(~,~)ver(-60,25));

crearBoton('Superior',0.76,0, ...
    @(~,~)ver(0,90));

crearBoton('Inferior',0.67,0, ...
    @(~,~)ver(0,-90));

crearBoton('Az 0',0.56,1, ...
    @(~,~)ver(0,0));

crearBoton('Az 90',0.56,2, ...
    @(~,~)ver(90,0));

crearBoton('Az 180',0.47,1, ...
    @(~,~)ver(180,0));

crearBoton('Az -90',0.47,2, ...
    @(~,~)ver(-90,0));

crearBoton('Girar izquierda',0.34,1, ...
    @(~,~)rotar(-15,0));

crearBoton('Girar derecha',0.34,2, ...
    @(~,~)rotar(15,0));

crearBoton('Inclinar arriba',0.25,1, ...
    @(~,~)rotar(0,15));

crearBoton('Inclinar abajo',0.25,2, ...
    @(~,~)rotar(0,-15));

uicontrol( ...
    'Parent',panel, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.06 0.14 0.88 0.07], ...
    'String','Tambien puedes rotar con el mouse.', ...
    'HorizontalAlignment','center');

btnGIF3D = uicontrol( ...
    'Parent',panel, ...
    'Style','pushbutton', ...
    'Units','normalized', ...
    'Position',[0.09 0.035 0.82 0.085], ...
    'String','Exportar GIF 3D', ...
    'FontSize',10);

rotate3d(g.figura3D,'on');

%% 5. TRAYECTORIAS MATERIALES DEL FONEMA /s/

figRuta = figure( ...
    'Name','Fonema /s/ laminal - Trayectorias de puntos linguales', ...
    'NumberTitle','off', ...
    'Color','w', ...
    'Units','pixels', ...
    'Position',[80 60 1450 820]);

uicontrol(figRuta, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.04 0.935 0.92 0.045], ...
    'String','Fonema /s/ laminal - Trayectorias de puntos linguales', ...
    'BackgroundColor','w', ...
    'FontSize',15, ...
    'FontWeight','bold');

%% PANEL IZQUIERDO: CONTEXTO SAGITAL

axRuta = axes( ...
    'Parent',figRuta, ...
    'Units','normalized', ...
    'Position',[0.055 0.245 0.535 0.63]);

hold(axRuta,'on');

R = sistema.contactoSagital.regiones;

for r = 1:numel(R)

    B = R(r);

    ok = B.valido(:) & ...
        isfinite(B.y(:)) & ...
        isfinite(B.zSuperior(:));

    if nnz(ok)<2
        continue
    end

    plot(axRuta,B.y(ok),B.zSuperior(ok), ...
        '-','Color',B.color, ...
        'LineWidth',1.4, ...
        'HandleVisibility','off');

end

S0 = sistema.lengua0.sagital;

plot(axRuta,S0.y,S0.zSuperior, ...
    'k--','LineWidth',1.5, ...
    'DisplayName','Dorso inicial');

plot(axRuta,Sfinal.ySuperior,Sfinal.zSuperior, ...
    'r-','LineWidth',2.2, ...
    'DisplayName','Dorso final /s/');

%% TRAYECTORIAS DE LOS SEIS PUNTOS

colores = lines(np);

hActual = gobjects(np,1);
hRutas = gobjects(np,1);

for j = 1:np

    Y = reshape(tray.puntos(:,j,1),[],1);
    Z = reshape(tray.puntos(:,j,2),[],1);

    hRutas(j) = plot(axRuta,Y,Z,'--', ...
        'Color',colores(j,:), ...
        'LineWidth',1.5, ...
        'DisplayName',tray.nombres{j});

    % Posicion inicial.
    plot(axRuta,Y(1),Z(1),'o', ...
        'Color',colores(j,:), ...
        'MarkerSize',6, ...
        'HandleVisibility','off');

    % Posicion final.
    plot(axRuta,Y(end),Z(end),'o', ...
        'Color',colores(j,:), ...
        'MarkerFaceColor',colores(j,:), ...
        'MarkerSize',7, ...
        'HandleVisibility','off');

    % Marcador animado.
    hActual(j) = plot(axRuta,Y(1),Z(1),'o', ...
        'MarkerEdgeColor','k', ...
        'MarkerFaceColor',colores(j,:), ...
        'MarkerSize',10, ...
        'HandleVisibility','off');

end

set(axRuta,'XDir','reverse');

axis(axRuta,'equal');
grid(axRuta,'on');

xlabel(axRuta,'Y longitudinal (mm)');
ylabel(axRuta,'Z vertical (mm)');

title(axRuta, ...
    'Desplazamientos linguales en el plano sagital', ...
    'FontSize',11);

legend(axRuta, ...
    'Location','southoutside', ...
    'NumColumns',2, ...
    'FontSize',9);


%% PANEL DERECHO: SELECCION DE PUNTO

uicontrol(figRuta, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.655 0.895 0.31 0.030], ...
    'String','Seleccionar punto lingual:', ...
    'HorizontalAlignment','left', ...
    'BackgroundColor','w', ...
    'FontSize',11, ...
    'FontWeight','bold');

btnPuntos = gobjects(np,1);

for j = 1:np

    btnPuntos(j) = uicontrol( ...
        'Parent',figRuta, ...
        'Style','pushbutton', ...
        'Units','normalized', ...
        'Position',[0.655+(j-1)*0.052 0.837 0.043 0.045], ...
        'String',char(9679), ...
        'ForegroundColor',colores(j,:), ...
        'BackgroundColor',[0.94 0.94 0.94], ...
        'FontSize',16, ...
        'FontWeight','bold', ...
        'TooltipString',tray.nombres{j}, ...
        'UserData',j, ...
        'Callback',@(src,~)mostrarDetalle( ...
        get(src,'UserData')));

end

txtPunto = uicontrol(figRuta, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.655 0.785 0.31 0.035], ...
    'String','', ...
    'HorizontalAlignment','left', ...
    'BackgroundColor','w', ...
    'FontSize',11, ...
    'FontWeight','bold');

%% GRAFICO DETALLADO

axDetalle = axes( ...
    'Parent',figRuta, ...
    'Units','normalized', ...
    'Position',[0.655 0.415 0.315 0.355]);

hold(axDetalle,'on');
grid(axDetalle,'on');

set(axDetalle,'XDir','reverse');

xlabel(axDetalle,'Y longitudinal (mm)');
ylabel(axDetalle,'Z vertical (mm)');

%% ECUACIONES PARAMETRICAS

uicontrol(figRuta, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.655 0.335 0.32 0.030], ...
    'String','Ecuaciones de movimiento del punto seleccionado', ...
    'BackgroundColor','w', ...
    'HorizontalAlignment','left', ...
    'FontSize',10, ...
    'FontWeight','bold');

txtEcuaciones = uicontrol(figRuta, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.655 0.100 0.325 0.225], ...
    'String','', ...
    'BackgroundColor','w', ...
    'HorizontalAlignment','left', ...
    'FontName','Consolas', ...
    'FontSize',9);

%% NOTA INFERIOR

uicontrol(figRuta, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.055 0.012 0.91 0.075], ...
    'String',{ ...
    's: posicion longitudinal normalizada sobre la lengua del modelo; s=0 corresponde a la punta y s=1 al extremo posterior.', ...
    'La coordenada s no representa tiempo ni distancia en mm. u: progreso del movimiento, desde reposo (0) hasta /s/ final (1).', ...
    'Linea discontinua: trayectoria FEM. Circulo vacio: inicio; cuadrado relleno: final; rombo: posicion actual. Regreso por el mismo recorrido.'}, ...
    'BackgroundColor','w', ...
    'HorizontalAlignment','left', ...
    'FontSize',9);

%% ESTADO DEL PANEL DETALLADO

indicePuntoActivo = 1;
hDetalleActual = gobjects(1);

mostrarDetalle(1);

%% 6. VALIDACION FEM DE LA TRAYECTORIA

figFEM = figure( ...
    'Color','w', ...
    'Name','/s/ laminal - Evaluacion FEM de la trayectoria', ...
    'NumberTitle','off', ...
    'Position',[120 70 1200 800]);

tFEM = tiledlayout(figFEM,2,1, ...
    'TileSpacing','loose', ...
    'Padding','loose');

% Reservar espacio inferior para la nota tecnica.
tFEM.Units = 'normalized';
tFEM.OuterPosition = [0.045 0.15 0.91 0.83];

u = tray.u(:);

G = tray.green(:);
Jmin = tray.jmin(:);
Jmax = tray.jmax(:);

limites = tray.simulaciones{end}.validacion.limites;

limGreen = limites.GreenMax;
limJmin = limites.Jmin;
limJmax = limites.Jmax;

%% PANEL SUPERIOR: DEFORMACION MAXIMA

axG = nexttile(tFEM);
hold(axG,'on');

hG = plot(axG,u,G, ...
    'Color',[0.85 0.15 0.18], ...
    'LineWidth',2.5, ...
    'DisplayName','Deformacion maxima');

hLimG = yline(axG,limGreen,'--', ...
    'Color',[0.25 0.25 0.25], ...
    'LineWidth',1.8, ...
    'DisplayName','Limite exploratorio');

% Marcar los estados que exceden el limite.
fueraG = G>limGreen;

if any(fueraG)

    plot(axG,u(fueraG),G(fueraG),'rx', ...
        'MarkerSize',9, ...
        'LineWidth',2, ...
        'HandleVisibility','off');

end

% Cursor que indica el estado mostrado en el slider.
cursorG = xline(axG,0,':', ...
    'Color',[0.15 0.35 0.65], ...
    'LineWidth',1.5, ...
    'HandleVisibility','off');

xlim(axG,[0 1]);

ylim(axG,[0 max(1.2*limGreen, ...
    1.12*max(G))]);

grid(axG,'on');

xlabel(axG,'Progreso hacia /s/ (0 = reposo, 1 = final)');
ylabel(axG,'Green-Lagrange maximo');

title(axG, ...
    'Deformacion Green-Lagrange maxima durante la trayectoria /s/', ...
    'FontWeight','bold');

legend(axG,[hG hLimG], ...
    'Location','northwest');

%% PANEL INFERIOR: JACOBIANO

axJ = nexttile(tFEM);
hold(axJ,'on');

hMin = plot(axJ,u,Jmin, ...
    'Color',[0.10 0.40 0.80], ...
    'LineWidth',2.3, ...
    'DisplayName','Jacobiano minimo');

hMax = plot(axJ,u,Jmax, ...
    'Color',[0.15 0.60 0.35], ...
    'LineWidth',2.3, ...
    'DisplayName','Jacobiano maximo');

hLimInf = yline(axJ,limJmin,'--', ...
    'Color',[0.4 0.4 0.4], ...
    'LineWidth',1.5, ...
    'DisplayName','Limite inferior');

hLimSup = yline(axJ,limJmax,'--', ...
    'Color',[0.65 0.35 0.25], ...
    'LineWidth',1.5, ...
    'DisplayName','Limite superior');

% Marcar las infracciones del Jacobiano.
fueraJmin = Jmin<limJmin;
fueraJmax = Jmax>limJmax;

if any(fueraJmin)

    plot(axJ,u(fueraJmin),Jmin(fueraJmin), ...
        'rx','MarkerSize',9, ...
        'LineWidth',2, ...
        'HandleVisibility','off');

end

if any(fueraJmax)

    plot(axJ,u(fueraJmax),Jmax(fueraJmax), ...
        'rx','MarkerSize',9, ...
        'LineWidth',2, ...
        'HandleVisibility','off');

end

cursorJ = xline(axJ,0,':', ...
    'Color',[0.15 0.35 0.65], ...
    'LineWidth',1.5, ...
    'HandleVisibility','off');

xlim(axJ,[0 1]);

margen = 0.03;

ylim(axJ,[ ...
    min([Jmin;limJmin])-margen, ...
    max([Jmax;limJmax])+margen]);

grid(axJ,'on');

xlabel(axJ,'Progreso hacia /s/ (0 = reposo, 1 = final)');
ylabel(axJ,'Jacobiano de deformacion J');

title(axJ, ...
    'Evolucion del Jacobiano de deformacion durante la trayectoria /s/', ...
    'FontWeight','bold');

legend(axJ,[hMin hMax hLimInf hLimSup], ...
    'Location','best');

%% TITULO Y RESULTADO GENERAL

nValidos = nnz(tray.cumpleFEM);
nTotal = numel(tray.cumpleFEM);

if nValidos==nTotal

    resultado = 'TODOS LOS ESTADOS CUMPLEN FEM';

else

    resultado = sprintf( ...
        '%d ESTADOS NO CUMPLEN FEM', ...
        nTotal-nValidos);

end

%% TITULO GENERAL
title(tFEM,sprintf( ...
    ['/s/ laminal - Evaluacion numerica FEM ', ...
     '(%d/%d estados admisibles)'], ...
    nValidos,nTotal), ...
    'FontSize',13, ...
    'FontWeight','bold');

%% NOTA DE INTERPRETACION
uicontrol(figFEM, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.07 0.020 0.86 0.085], ...
    'String',{ ...
        'Green-Lagrange: cuantifica la magnitud maxima de deformacion local de la lengua.', ...
        'Jacobiano J: caracteriza el cambio local de area y permite detectar deformaciones inadmisibles o inversiones.', ...
        'Ambos son resultados del FEM; se contrastan con criterios numericos exploratorios, no clinicos.'}, ...
    'BackgroundColor','w', ...
    'HorizontalAlignment','left', ...
    'FontSize',9, ...
    'ForegroundColor',[0.30 0.30 0.30]);

%% 7. ASIGNAR CALLBACKS

slider.Callback = @(src,~) ...
    mostrar(round(get(src,'Value')));

btnPlay.Callback = @(~,~) reproducir();

btnGIF2D.Callback = @(~,~) exportarGIF('2D');
btnGIF3D.Callback = @(~,~) exportarGIF('3D');

%% 8. ESTADO INICIAL

mostrar(1);

%% 9. DEVOLVER IDENTIFICADORES

interfaz = struct();

interfaz.figuraSagital = g.figuraSagital;
interfaz.figura3D = g.figura3D;
interfaz.figuraTrayectorias = figRuta;

interfaz.axTrayectorias = axRuta;
interfaz.axDetalle = axDetalle;
interfaz.botonesPuntos = btnPuntos;
interfaz.textoEcuaciones = txtEcuaciones;

interfaz.figuraFEM = figFEM;
interfaz.indicesCiclo = indicesCiclo;
interfaz.modoRecorrido = modoRecorrido;

interfaz.slider = slider;
interfaz.graficos = g;

%% =====================================================
% FUNCIONES LOCALES INTERACTIVAS
% ======================================================

    %% SELECCIONAR UN PUNTO MATERIAL

    
    function mostrarDetalle(j)

        indicePuntoActivo = j;

        Y = reshape(tray.puntos(:,j,1),[],1);
        Z = reshape(tray.puntos(:,j,2),[],1);

        %% LIMPIAR COMPLETAMENTE EL GRAFICO ANTERIOR

        legend(axDetalle,'off');
        cla(axDetalle,'reset');

        set(axDetalle, ...
            'Units','normalized', ...
            'Position',[0.655 0.415 0.315 0.355]);

        hold(axDetalle,'on');
        grid(axDetalle,'on');

        color = colores(j,:);

        %% TRAYECTORIA DEL PUNTO SELECCIONADO

        hTrayectoria = plot(axDetalle,Y,Z,'--', ...
            'Color',color, ...
            'LineWidth',2.7, ...
            'DisplayName','Trayectoria');

        %% POSICION INICIAL

        hInicio = plot(axDetalle,Y(1),Z(1),'o', ...
            'MarkerEdgeColor',color, ...
            'MarkerFaceColor','w', ...
            'MarkerSize',9, ...
            'LineWidth',1.8, ...
            'DisplayName','Inicio: reposo');

        %% POSICION FINAL

        hFinal = plot(axDetalle,Y(end),Z(end),'s', ...
            'MarkerEdgeColor',color, ...
            'MarkerFaceColor',color, ...
            'MarkerSize',9, ...
            'LineWidth',1.5, ...
            'DisplayName','Final: /s/');

        %% MARCADOR DE LA POSICION ACTUAL

        kSlider = round(get(slider,'Value'));
        kSlider = max(1,min(nCiclo,kSlider));

        iFEM = indicesCiclo(kSlider);

        hDetalleActual = plot(axDetalle, ...
            Y(iFEM),Z(iFEM),'d', ...
            'MarkerEdgeColor','k', ...
            'MarkerFaceColor','w', ...
            'MarkerSize',9, ...
            'LineWidth',1.8, ...
            'HandleVisibility','off');

        %% ENCUADRAR AUTOMATICAMENTE CADA TRAYECTORIA

        rangoY = max(Y)-min(Y);
        rangoZ = max(Z)-min(Z);

        margenY = max(0.50,0.18*rangoY);
        margenZ = max(0.50,0.18*rangoZ);

        % Evitar que un desplazamiento horizontal o vertical
        % quede fuera de la ventana por una escala degenerada.
        axis(axDetalle,'normal');

        xlim(axDetalle, ...
            [min(Y)-margenY,max(Y)+margenY]);

        ylim(axDetalle, ...
            [min(Z)-margenZ,max(Z)+margenZ]);

        set(axDetalle, ...
            'XDir','reverse', ...
            'DataAspectRatioMode','auto', ...
            'PlotBoxAspectRatioMode','auto');

        xlabel(axDetalle,'Y longitudinal (mm)');
        ylabel(axDetalle,'Z vertical (mm)');

        title(axDetalle, ...
            sprintf('Trayectoria de %s',tray.nombres{j}), ...
            'FontSize',11, ...
            'Interpreter','none');

        %% LEYENDA

        lgd = legend(axDetalle, ...
            [hTrayectoria,hInicio,hFinal], ...
            {'Recorrido','Inicio: reposo','Final: /s/'}, ...
            'Location','southoutside', ...
            'Orientation','horizontal', ...
            'NumColumns',3, ...
            'FontSize',9);

        lgd.Box = 'off';
        lgd.AutoUpdate = 'off';

        %% RESALTAR EL PUNTO SELECCIONADO EN EL PANEL IZQUIERDO

        for k = 1:np

            if ~isgraphics(hRutas(k))
                continue
            end

            if k==j

                set(hRutas(k),'LineWidth',2.8);

                set(btnPuntos(k), ...
                    'BackgroundColor',[0.82 0.87 0.95]);

            else

                set(hRutas(k),'LineWidth',1.5);

                set(btnPuntos(k), ...
                    'BackgroundColor',[0.94 0.94 0.94]);

            end

        end

        %% INFORMACION DEL PUNTO

        set(txtPunto,'String',sprintf( ...
            '%s | s = %.2f', ...
            tray.nombres{j},tray.sMarcas(j)));

        %% ECUACIONES PARAMETRICAS EXISTENTES

        cY = tray.ecuaciones.coefY{j};
        cZ = tray.ecuaciones.coefZ{j};

        [y1,y2] = formatearEcuacion(cY,'Y');
        [z1,z2] = formatearEcuacion(cZ,'Z');

        rmseY = tray.ecuaciones.rmse(j,1);
        rmseZ = tray.ecuaciones.rmse(j,2);

        set(txtEcuaciones,'String',{ ...
            y1; ...
            y2; ...
            ' '; ...
            z1; ...
            z2; ...
            ' '; ...
            sprintf('RMSE Y = %.5f mm | RMSE Z = %.5f mm', ...
                rmseY,rmseZ); ...
            'u = 0: reposo | u = 1: /s/ final'});

        drawnow limitrate;

    end

    %% FORMATEAR LOS COEFICIENTES POLINOMICOS

    function [linea1,linea2] = formatearEcuacion(c,nombre)

        c = c(:)';
        nc = numel(c);

        terminos = cell(1,nc);

        for k = 1:nc

            potencia = nc-k;
            valor = abs(c(k));

            if potencia==0

                base = sprintf('%.4g',valor);

            elseif potencia==1

                base = sprintf('%.4g*u',valor);

            else

                base = sprintf( ...
                    '%.4g*u^%d',valor,potencia);

            end

            if k==1

                if c(k)<0
                    terminos{k} = ['-',base];
                else
                    terminos{k} = base;
                end

            else

                if c(k)<0
                    terminos{k} = ['- ',base];
                else
                    terminos{k} = ['+ ',base];
                end

            end

        end

        mitad = ceil(nc/2);

        linea1 = sprintf('%s(u) = %s', ...
            nombre,strjoin(terminos(1:mitad),' '));

        linea2 = ['       ', ...
            strjoin(terminos(mitad+1:end),' ')];

    end

    function crearBoton(nombre,y,columna,accion)

        if columna==0

            x = 0.09;
            w = 0.82;

        elseif columna==1

            x = 0.09;
            w = 0.38;

        else

            x = 0.53;
            w = 0.38;

        end

        uicontrol( ...
            'Parent',panel, ...
            'Style','pushbutton', ...
            'Units','normalized', ...
            'Position',[x y w 0.075], ...
            'String',nombre, ...
            'Callback',accion);

    end

    function ver(az,el)

        if ~isgraphics(g.ax3D)
            return
        end

        view(g.ax3D,[az el]);
        drawnow;

    end

    function rotar(deltaAz,deltaEl)

        if ~isgraphics(g.ax3D)
            return
        end

        [az,el] = view(g.ax3D);

        el = max(-90,min(90,el+deltaEl));

        view(g.ax3D,[az+deltaAz el]);
        drawnow;

    end


    function mostrar(k)

        if ~isgraphics(g.figuraSagital) || ...
                ~isgraphics(g.figura3D)
            return
        end

        % Fotograma dentro del ciclo completo.
        k = max(1,min(nCiclo,round(k)));

        % Estado FEM original que corresponde al fotograma.
        iFEM = indicesCiclo(k);

        sim = tray.simulaciones{iFEM};
        ana = tray.analisis{iFEM};

        g = actualizar_visualizacion( ...
            g,sistema,sim,ana);

        if isgraphics(slider)
            set(slider,'Value',k);
        end

        if k<=n
            fase = 'Ida';
        else
            fase = 'Regreso';
        end

        if isgraphics(estadoTexto)

            mensaje = sprintf( ...
                ['%s | Fotograma %d/%d | FEM %d/%d | ', ...
                'Green %.4f | Jmin %.4f | Cumple %d'], ...
                fase,k,nCiclo,iFEM,n, ...
                tray.green(iFEM), ...
                tray.jmin(iFEM), ...
                tray.cumpleFEM(iFEM));

            set(estadoTexto,'String',mensaje);

        end

        % Actualizar los seis puntos en la vista general.
        for j = 1:np

            if isgraphics(hActual(j))

                set(hActual(j), ...
                    'XData',tray.puntos(iFEM,j,1), ...
                    'YData',tray.puntos(iFEM,j,2));

            end

        end

        % Actualizar el punto elegido en la vista detallada.
        if isgraphics(hDetalleActual)

            j = indicePuntoActivo;

            set(hDetalleActual, ...
                'XData',tray.puntos(iFEM,j,1), ...
                'YData',tray.puntos(iFEM,j,2));

        end

        % Cursores de la figura FEM.
        progreso = tray.u(iFEM);

        if isgraphics(cursorG)
            set(cursorG,'Value',progreso);
        end

        if isgraphics(cursorJ)
            set(cursorJ,'Value',progreso);
        end

        drawnow limitrate;

    end


    function reproducir()

        if ~isgraphics(slider)
            return
        end

        % 1 = ida y regreso; 2 = solo ida.
        modo = get(modoRecorrido,'Value');

        if modo==1
            nFotogramas = nCiclo;
        else
            nFotogramas = n;
        end

        set(btnPlay,'Enable','off');

        % Duracion de cada tramo, no duracion fisiologica.
        pausa = cfg.trayectoriaS.duracionVisual_s/ ...
            max(n-1,1);

        try

            for k = 1:nFotogramas

                if ~isgraphics(slider)
                    break
                end

                mostrar(k);
                pause(pausa);

            end

        catch ME

            if isgraphics(btnPlay)
                set(btnPlay,'Enable','on');
            end

            rethrow(ME);

        end

        if isgraphics(btnPlay)
            set(btnPlay,'Enable','on');
        end

    end

    
    function exportarGIF(tipo)
    
        % Determinar tipo de movimiento.
        modo = get(modoRecorrido,'Value');
    
        if modo==1
            nFotogramas = nCiclo;
            sufijo = '_ciclo';
        else
            nFotogramas = n;
            sufijo = '_ida';
        end
    
        %% Seleccionar figura
    
        if strcmp(tipo,'3D')
    
            eje = g.ax3D;
            figObjetivo = g.figura3D;
    
            nombreDefault = ...
                ['trayectoria_s_3D' sufijo '.gif'];
    
        else
    
            eje = g.axSagital;
            figObjetivo = g.figuraSagital;
    
            nombreDefault = ...
                ['trayectoria_s_sagital' sufijo '.gif'];
    
        end
    
        %% Archivo de salida
    
        [nombre,ruta] = uiputfile( ...
            '*.gif', ...
            'Guardar trayectoria /s/', ...
            nombreDefault);
    
        if isequal(nombre,0)
            return
        end
    
        archivo = fullfile(ruta,nombre);
    
        fps = cfg.trayectoriaS.fpsGIF;
    
        validateattributes(fps,{'numeric'}, ...
            {'scalar','positive','finite'});
    
        %% Preparar interfaz
    
        kAnterior = round(get(slider,'Value'));
    
        botones = [ ...
            btnGIF2D, ...
            btnGIF3D, ...
            btnPlay, ...
            slider, ...
            modoRecorrido];
    
        botones = botones(isgraphics(botones));
    
        if ~isempty(botones)
            set(botones,'Enable','off');
        end
    
        %% Generar GIF
    
        try
    
            figure(figObjetivo);
    
            for k = 1:nFotogramas
    
                mostrar(k);
                drawnow;
    
                % Conserva la orientacion 3D seleccionada.
                captura = getframe(eje);
    
                RGB = frame2im(captura);
    
                [I,mapa] = rgb2ind(RGB,256);
    
                if k==1
    
                    imwrite(I,mapa,archivo, ...
                        'gif', ...
                        'LoopCount',Inf, ...
                        'DelayTime',1/fps);
    
                else
    
                    imwrite(I,mapa,archivo, ...
                        'gif', ...
                        'WriteMode','append', ...
                        'DelayTime',1/fps);
    
                end
    
            end
    
            fprintf('\n===== GIF EXPORTADO =====\n');
            fprintf('Archivo: %s\n',archivo);
            fprintf('Fotogramas: %d\n',nFotogramas);
    
        catch ME
    
            warning('Error al exportar GIF: %s', ...
                ME.message);
    
        end
    
        %% Restaurar estado anterior
    
        if isgraphics(slider)
            mostrar(kAnterior);
        end
    
        botones = botones(isgraphics(botones));
    
        if ~isempty(botones)
            set(botones,'Enable','on');
        end
    
    end

end
