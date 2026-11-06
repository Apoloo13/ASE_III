
function fig = visualizar_evidencia_r_multiple(d)
% Compara imagenes instrumentales de /r/ con el perfil MATLAB.
% Permite marcar, corregir, confirmar y borrar contornos.
% La comparacion es morfologica, no metrica ni clinica.

%% 1. DATOS Y RUTAS

campos = { ...
    's','P0','PF','punta', ...
    'gapDental','gapAlveolar', ...
    'sDental','sAlveolar', ...
    'distanciaPuntaAlveolar'};

for k = 1:numel(campos)
    assert(isfield(d,campos{k}), ...
        'Falta el campo evi.%s.',campos{k});
end

raiz = fileparts(fileparts(mfilename('fullpath')));
carpeta = fullfile(raiz,'referencias_clinicas');

archivos = {
    fullfile(carpeta,'r_multiple_elie_laprie_2017.png')
};

matrices = {
    fullfile(carpeta,'trazo_r_multiple_elie_laprie_2017.mat')
};

nombres = {
    '/r/ multiple - Elie y Laprie (2017)'
};

nRef = numel(archivos);
trazos = cell(nRef,1);

for k = 1:nRef

    if ~isfile(matrices{k})
        continue
    end

    try
        S = load(matrices{k},'trazo');

        if isfield(S,'trazo') && ...
                isnumeric(S.trazo) && ...
                size(S.trazo,2)==2 && ...
                size(S.trazo,1)>=4 && ...
                all(isfinite(S.trazo(:)))

            trazos{k} = S.trazo;
        end

    catch ME
        warning('No se pudo leer el trazo %d: %s', ...
            k,ME.message);
    end

end

%% 2. PERFIL DEL SIMULADOR

s0 = d.s(:);

[s0,ord] = sort(s0);
P0 = d.P0(ord,:);
PF = d.PF(ord,:);

[s0,iu] = unique(s0,'stable');
P0 = P0(iu,:);
PF = PF(iu,:);


% Intervalo anterior comparable de la lengua.
% s = 0 corresponde a la punta.
% s aumenta hacia la region posterior.

sInicio = 0.00;
sFin = 0.22;

sModelo = linspace(sInicio,sFin,180)';

Q0 = interp1(s0,P0,sModelo,'linear');
QF = interp1(s0,PF,sModelo,'linear');

% En MATLAB, Y disminuye hacia posterior.
% Se invierte Y para que ambos perfiles avancen
% desde la punta hacia la parte posterior.

Q0comparacion = [-Q0(:,1), Q0(:,2)];
QFcomparacion = [-QF(:,1), QF(:,2)];

% Registrar ambos perfiles respecto a sus
% respectivos extremos anterior y posterior.

[tF,hF] = registrar_contorno_r(QFcomparacion);
[t0,h0] = registrar_contorno_r(Q0comparacion);

%% 3. ESTADO DE EDICION

capturando = false;
indiceCaptura = 0;

puntosTemporales = zeros(0,2);
hTemporal = gobjects(0);

%% 4. FIGURA

fig = figure( ...
    'Color','w', ...
    'NumberTitle','off', ...
    'Name','/r/ - evidencia instrumental y comparacion morfologica', ...
    'Units','pixels', ...
    'Position',[80 60 1380 790]);

uicontrol(fig, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.035 0.944 0.93 0.040], ...
    'String', ...
    '/r/ - resonancias de referencia y comparacion con el modelo lingual', ...
    'BackgroundColor','w', ...
    'HorizontalAlignment','left', ...
    'FontSize',15, ...
    'FontWeight','bold');

%% 5. CONTROLES SUPERIORES

uicontrol(fig, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.035 0.884 0.080 0.030], ...
    'String','Referencia:', ...
    'BackgroundColor','w', ...
    'HorizontalAlignment','left', ...
    'FontSize',10);

sel = uicontrol(fig, ...
    'Style','popupmenu', ...
    'Units','normalized', ...
    'Position',[0.115 0.884 0.228 0.038], ...
    'String',nombres, ...
    'Value',1, ...
    'FontSize',10, ...
    'Callback',@refrescar);

botMarcar = uicontrol(fig, ...
    'Style','pushbutton', ...
    'Units','normalized', ...
    'Position',[0.354 0.879 0.124 0.044], ...
    'String','Marcar contorno', ...
    'FontSize',10, ...
    'Callback',@iniciarCaptura);

botBorrar = uicontrol(fig, ...
    'Style','pushbutton', ...
    'Units','normalized', ...
    'Position',[0.486 0.879 0.100 0.044], ...
    'String','Borrar trazo', ...
    'FontSize',10, ...
    'Callback',@borrarTrazo);

botTerminar = uicontrol(fig, ...
    'Style','pushbutton', ...
    'Units','normalized', ...
    'Position',[0.600 0.879 0.150 0.044], ...
    'String','Terminar y revisar', ...
    'FontSize',10, ...
    'Visible','off', ...
    'Callback',@terminarCaptura);

botDeshacer = uicontrol(fig, ...
    'Style','pushbutton', ...
    'Units','normalized', ...
    'Position',[0.760 0.879 0.100 0.044], ...
    'String','Deshacer punto', ...
    'FontSize',10, ...
    'Visible','off', ...
    'Callback',@deshacerPunto);

botCancelar = uicontrol(fig, ...
    'Style','pushbutton', ...
    'Units','normalized', ...
    'Position',[0.870 0.879 0.092 0.044], ...
    'String','Cancelar', ...
    'FontSize',10, ...
    'Visible','off', ...
    'Callback',@cancelarCaptura);

%% 6. EJES

axFoto = axes( ...
    'Parent',fig, ...
    'Units','normalized', ...
    'Position',[0.055 0.445 0.425 0.398]);

axPerfil = axes( ...
    'Parent',fig, ...
    'Units','normalized', ...
    'Position',[0.558 0.484 0.397 0.342]);

%% 7. OPCIONES DE VISUALIZACION

cbTrazo = uicontrol(fig, ...
    'Style','checkbox', ...
    'Units','normalized', ...
    'Position',[0.050 0.395 0.205 0.034], ...
    'String','Mostrar contorno verde', ...
    'Value',1, ...
    'BackgroundColor','w', ...
    'FontSize',10, ...
    'Callback',@refrescar);

cbZoom = uicontrol(fig, ...
    'Style','checkbox', ...
    'Units','normalized', ...
    'Position',[0.266 0.395 0.205 0.034], ...
    'String','Acercamiento clinico', ...
    'Value',0, ...
    'BackgroundColor','w', ...
    'FontSize',10, ...
    'Callback',@refrescar);

cbModelo = uicontrol(fig, ...
    'Style','checkbox', ...
    'Units','normalized', ...
    'Position',[0.550 0.398 0.175 0.032], ...
    'String','Perfil simulado', ...
    'Value',1, ...
    'BackgroundColor','w', ...
    'FontSize',10, ...
    'Callback',@refrescar);

cbInicial = uicontrol(fig, ...
    'Style','checkbox', ...
    'Units','normalized', ...
    'Position',[0.738 0.398 0.215 0.032], ...
    'String','Referencia inicial', ...
    'Value',0, ...
    'BackgroundColor','w', ...
    'FontSize',10, ...
    'Callback',@refrescar);

%% 8. INFORMACION Y TABLA

info = uicontrol(fig, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.045 0.342 0.915 0.039], ...
    'String','Seleccione una imagen para visualizar su contorno.', ...
    'BackgroundColor','w', ...
    'HorizontalAlignment','left', ...
    'FontSize',10);

tabla = uitable(fig, ...
    'Units','normalized', ...
    'Position',[0.046 0.100 0.918 0.226], ...
    'Data',cell(4,3), ...
    'ColumnName',{ ...
        'Rasgo comparado', ...
        'Resultado MATLAB', ...
        'Interpretacion'}, ...
    'ColumnWidth',{260 370 550}, ...
    'RowName',[], ...
    'FontSize',10);

uicontrol(fig, ...
    'Style','text', ...
    'Units','normalized', ...
    'Position',[0.048 0.020 0.915 0.072], ...
    'String',{ ...
        'Referencia: Elie y Laprie (2017). Imagen sagital del fonema /r/ multiple.', ...
        'La imagen se refleja horizontalmente para homologarla con la orientacion longitudinal usada en MATLAB.', ...
        'El contorno se alinea por sus extremos y se normaliza para comparar su forma relativa; no demuestra contacto 3D ni vibracion.'}, ...
    'BackgroundColor','w', ...
    'HorizontalAlignment','left', ...
    'FontSize',9);

%% 9. INICIALIZAR

refrescar([],[]);

%% =====================================================
% ACTUALIZAR VISUALIZACION
% ======================================================

    function refrescar(~,~)

        if capturando
            return
        end

        indice = get(sel,'Value');

        % Ambas referencias son resonancias sagitales.
        % SP1 y SP2 permiten marcar y borrar contornos.

        set([botMarcar botBorrar],'Enable','on');

        legend(axPerfil,'off');

        cla(axFoto);
        cla(axPerfil);

        hold(axFoto,'on');
        hold(axPerfil,'on');

        %% Imagen instrumental

        if isfile(archivos{indice})

            I = imread(archivos{indice});
            I = fliplr(I); 

            alto = size(I,1);
            ancho = size(I,2);

            image(axFoto,[1 ancho],[1 alto],I);

            set(axFoto,'YDir','reverse');

            axis(axFoto,'image');

            if get(cbZoom,'Value') && indice==1

                xlim(axFoto,[floor(0.49*ancho) ancho]);
                ylim(axFoto,[floor(0.09*alto) ...
                             ceil(0.78*alto)]);

            else

                xlim(axFoto,[1 ancho]);
                ylim(axFoto,[1 alto]);

            end

            set(axFoto,'XTick',[],'YTick',[]);

            title(axFoto,nombres{indice}, ...
                'FontSize',11);

        else

            axis(axFoto,[0 1 0 1]);

            text(axFoto,0.05,0.55, ...
                sprintf('Imagen no encontrada:\n%s', ...
                archivos{indice}), ...
                'Interpreter','none');

            title(axFoto,'Imagen no disponible');

        end

        %% Contorno guardado

        trazo = trazos{indice};

        % Solo la resonancia permite comparar
        % un contorno sagital digitalizado.
        hayTrazo = isfile(archivos{indice}) && ...
            size(trazo,1)>=4;

        verde = [0.04 0.72 0.19];

        if hayTrazo && get(cbTrazo,'Value')

            plot(axFoto, ...
                trazo(:,1),trazo(:,2),'-', ...
                'Color',verde, ...
                'LineWidth',3.0);

            plot(axFoto, ...
                trazo(1,1),trazo(1,2),'o', ...
                'MarkerFaceColor',[0.95 0.2 0.18], ...
                'MarkerEdgeColor','w', ...
                'MarkerSize',8);

            plot(axFoto, ...
                trazo(end,1),trazo(end,2),'o', ...
                'MarkerFaceColor',verde, ...
                'MarkerEdgeColor','w', ...
                'MarkerSize',7);

        end

        %% COMPARACION MORFOLOGICA REGISTRADA
        
        % Las curvas se representan en coordenadas locales:
        %
        % t = posicion longitudinal normalizada.
        % h = desviacion perpendicular respecto a la
        %     recta que une los extremos del segmento.
        %
        % No representan alturas absolutas en mm.
        
        alturasVisibles = [];
        
        %% PERFIL SIMULADO
        
        if get(cbModelo,'Value')
        
            plot(axPerfil,tF,hF,'r-', ...
                'LineWidth',2.6, ...
                'DisplayName','Perfil simulado (MATLAB)');
        
            alturasVisibles = [alturasVisibles;hF(:)];
        
        end
        
        %% CONFIGURACION INICIAL OPCIONAL
        
        if get(cbInicial,'Value')
        
            plot(axPerfil,t0,h0,'--', ...
                'Color',[0.48 0.48 0.48], ...
                'LineWidth',1.7, ...
                'DisplayName','Configuracion inicial');
        
            alturasVisibles = [alturasVisibles;h0(:)];
        
        end
        
        %% CONTORNO CLINICO DIGITALIZADO
        
        if hayTrazo && get(cbTrazo,'Value')
        
            % Los puntos guardados estan en pixeles.
            % La coordenada Y de imagen crece hacia abajo.
            % Se invierte para que arriba sea positivo.
        
            Pclinico = [
                trazo(:,1), ...
                -trazo(:,2)
            ];
        
            % Registro local de la resonancia.
            [tC,hC] = registrar_contorno_r(Pclinico);
        
            plot(axPerfil,tC,hC,'-', ...
                'Color',verde, ...
                'LineWidth',2.7, ...
                'DisplayName','Contorno clinico - resonancia');
        
            alturasVisibles = [alturasVisibles;hC(:)];
        
        end
        
        %% REFERENCIA HORIZONTAL
        
        yline(axPerfil,0,':', ...
            'Color',[0.55 0.55 0.55], ...
            'LineWidth',1.0, ...
            'HandleVisibility','off');
        
        %% LIMITES GRAFICOS
        
        xlim(axPerfil,[-0.05 1.05]);
        
        if isempty(alturasVisibles)
        
            ylim(axPerfil,[-0.10 0.10]);
        
        else
        
            hMinimo = min([0;alturasVisibles]);
            hMaximo = max([0;alturasVisibles]);
        
            amplitud = hMaximo-hMinimo;
        
            margen = max(0.025,0.15*amplitud);
        
            ylim(axPerfil, ...
                [hMinimo-margen,hMaximo+margen]);
        
        end
        
        grid(axPerfil,'on');
        
        xlabel(axPerfil, ...
            'Posicion longitudinal normalizada (anterior a posterior)');
        
        ylabel(axPerfil, ...
            'Desviacion respecto al eje del segmento (adimensional)');
        
        %% TITULO CONTEXTUAL
        
        if hayTrazo && get(cbTrazo,'Value')
        
            title(axPerfil, ...
                '/r/ - Comparacion de la forma anterior');
        
        else
        
            title(axPerfil, ...
                '/r/ - Perfil anterior simulado');
        
        end
        
        %% Leyenda de perfiles

        if get(cbModelo,'Value') || ...
                get(cbInicial,'Value') || ...
                (hayTrazo && get(cbTrazo,'Value'))

            lgd = legend(axPerfil,'show', ...
                'Location','southeast', ...
                'FontSize',9);

            lgd.Box = 'on';
            lgd.AutoUpdate = 'off';

        end

        %% Mensaje de estado
        if hayTrazo

            mensaje = sprintf( ...
                ['%s: contorno clinico guardado (%d puntos). ', ...
                'Comparacion morfologica disponible.'], ...
                nombres{indice}, ...
                size(trazo,1));

        else

            if isfile(archivos{indice})

                mensaje = sprintf( ...
                    ['%s: sin contorno digitalizado. ', ...
                    'Seleccione "Marcar contorno" para comenzar.'], ...
                    nombres{indice});

            else

                mensaje = sprintf( ...
                    ['Imagen no disponible: %s. ', ...
                    'Coloque el archivo en referencias_clinicas.'], ...
                    nombres{indice});

            end

        end

        set(info,'String',mensaje);

        %% Tabla comparativa

        p08 = interp1(s0,PF,0.08,'linear');

        elevacion = p08(2)-d.punta(2);

        if isfield(d,'cumpleFEM') && d.cumpleFEM
            estadoFEM = 'Cumple criterios exploratorios';
        else
            estadoFEM = 'No cumple criterios exploratorios';
        end

        if hayTrazo
            estadoPerfil = 'Contorno disponible para comparacion';
        else
            estadoPerfil = 'Pendiente de digitalizacion';
        end

        datos = {

        'Referencia clinica activa', ...
        nombres{indice}, ...
        'Imagen sagital usada como referencia cualitativa del perfil lingual anterior';

        'Participacion anterior', ...
        sprintf('Alveolar: s=%.3f | Dist. punta-alveolo: %.3f mm', ...
        d.sAlveolar,d.distanciaPuntaAlveolar), ...
        'La maxima aproximacion del modelo ocurre en la zona apicoalveolar';

        'Proximidad sagital', ...
        sprintf('Dental: %.3f mm | Alveolar: %.3f mm', ...
        d.gapDental,d.gapAlveolar), ...
        'La postura es pre-vibratoria; la cercania 2D no demuestra vibracion ni contacto repetitivo';

        'Comparacion morfologica', ...
        estadoPerfil, ...
        'Se contrasta el trazo clinico manual contra el arco anterior simulado';

        'Admisibilidad biomecanica', ...
        estadoFEM, ...
        'La postura mostrada corresponde a una solucion FEM admisible';

        };

        set(tabla,'Data',datos);

    end

%% =====================================================
% INICIAR CAPTURA
% ======================================================

    function iniciarCaptura(~,~)

        if capturando
            return
        end

        indice = get(sel,'Value');

        if ~isfile(archivos{indice})

            errordlg( ...
                'No se encontro la imagen instrumental.', ...
                'Imagen faltante');

            return
        end

        capturando = true;
        indiceCaptura = indice;

        puntosTemporales = zeros(0,2);
        hTemporal = gobjects(0);

        %% Desactivar controles que cambiarian la imagen

        set([sel,botMarcar,botBorrar, ...
             cbTrazo,cbZoom,cbModelo,cbInicial], ...
            'Enable','off');

        set([botTerminar,botDeshacer,botCancelar], ...
            'Visible','on');

        %% Captura por eventos, sin ginput

        set(fig, ...
            'WindowButtonDownFcn',@registrarPunto, ...
            'WindowKeyPressFcn',@teclaCaptura);

        set(info,'String', ...
            ['Seleccione puntos sobre el dorso lingual. ', ...
             'Enter: revisar | Retroceso: deshacer | Esc: cancelar.']);

        title(axFoto, ...
            'Edicion activa: punta hacia posterior', ...
            'FontSize',11);

        figure(fig);

    end

%% =====================================================
% REGISTRAR CADA CLIC
% ======================================================

    function registrarPunto(~,~)

        if ~capturando
            return
        end

        % Aceptar solamente clic izquierdo.
        if ~strcmp(get(fig,'SelectionType'),'normal')
            return
        end

        objeto = get(fig,'CurrentObject');

        if isempty(objeto) || ~isgraphics(objeto)
            return
        end

        % Solo se permiten clics dentro del eje de la imagen.
        if isequal(objeto,axFoto)

            enImagen = true;

        else

            ejeObjeto = ancestor(objeto,'axes');
            enImagen = isequal(ejeObjeto,axFoto);

        end

        if ~enImagen
            return
        end

        punto = get(axFoto,'CurrentPoint');

        x = punto(1,1);
        y = punto(1,2);

        I = imread(archivos{indiceCaptura});

        ancho = size(I,2);
        alto = size(I,1);

        % Evitar puntos fuera de la imagen original.
        if x<1 || x>ancho || y<1 || y>alto
            return
        end

        % Evitar puntos duplicados consecutivos.
        if ~isempty(puntosTemporales)

            distancia = hypot( ...
                x-puntosTemporales(end,1), ...
                y-puntosTemporales(end,2));

            if distancia<1
                return
            end

        end

        puntosTemporales(end+1,:) = [x y];

        actualizarTrazoTemporal();

    end

%% =====================================================
% MOSTRAR TRAZO EN EDICION
% ======================================================

    function actualizarTrazoTemporal()

        if ~isempty(hTemporal)

            hValidos = hTemporal(isgraphics(hTemporal));

            if ~isempty(hValidos)
                delete(hValidos);
            end

        end

        hTemporal = gobjects(0);

        if isempty(puntosTemporales)

            set(info,'String', ...
                'Sin puntos. Haga clic sobre la imagen.');

            return
        end

        hTemporal = plot(axFoto, ...
            puntosTemporales(:,1), ...
            puntosTemporales(:,2), ...
            '-o', ...
            'Color',[0.03 0.85 0.23], ...
            'MarkerFaceColor',[0.03 0.85 0.23], ...
            'MarkerEdgeColor','w', ...
            'LineWidth',2.5, ...
            'MarkerSize',5);

        set(info,'String',sprintf( ...
            ['Editando %s | Puntos: %d | ', ...
             'Terminar para revisar antes de guardar.'], ...
            nombres{indiceCaptura}, ...
            size(puntosTemporales,1)));

        drawnow limitrate;

    end

%% =====================================================
% DESHACER ULTIMO PUNTO
% ======================================================

    function deshacerPunto(~,~)

        if ~capturando || isempty(puntosTemporales)
            return
        end

        puntosTemporales(end,:) = [];

        actualizarTrazoTemporal();

    end

%% =====================================================
% TECLAS DE EDICION
% ======================================================

    function teclaCaptura(~,evento)

        if ~capturando
            return
        end

        switch lower(evento.Key)

            case {'return','enter'}
                terminarCaptura([],[]);

            case {'backspace','delete'}
                deshacerPunto([],[]);

            case 'escape'
                cancelarCaptura([],[]);

        end

    end

%% =====================================================
% TERMINAR Y CONFIRMAR GUARDADO
% ======================================================

    function terminarCaptura(~,~)

        if ~capturando
            return
        end

        n = size(puntosTemporales,1);

        if n<4

            warndlg( ...
                'Seleccione al menos cuatro puntos antes de terminar.', ...
                'Trazo incompleto');

            return
        end

        longitud = sum(hypot( ...
            diff(puntosTemporales(:,1)), ...
            diff(puntosTemporales(:,2))));

        if longitud<5

            warndlg( ...
                'El trazo es demasiado corto.', ...
                'Trazo incompleto');

            return
        end

        %% Confirmacion

        respuesta = questdlg( ...
            sprintf([ ...
                'Se han marcado %d puntos.\n\n', ...
                '¿Desea guardar este contorno?\n', ...
                'Si existe uno anterior, sera reemplazado.'],n), ...
            'Confirmar contorno', ...
            'Guardar', ...
            'Seguir editando', ...
            'Descartar', ...
            'Seguir editando');

        switch respuesta

            case 'Guardar'

                trazo = puntosTemporales;

                try

                    if ~isfolder(carpeta)
                        mkdir(carpeta);
                    end

                    save(matrices{indiceCaptura},'trazo');

                catch ME

                    errordlg( ...
                        sprintf('No se pudo guardar:\n%s', ...
                        ME.message), ...
                        'Error de guardado');

                    return
                end

                % Actualizar solo despues de guardar correctamente.
                trazos{indiceCaptura} = trazo;

                set(cbTrazo,'Value',1);

                finalizarEdicion();

            case 'Descartar'

                % Mantiene intacto cualquier trazo anterior.
                finalizarEdicion();

            otherwise

                % Continuar con los puntos ya seleccionados.
                set(info,'String', ...
                    'Edicion reanudada. Puede anadir o deshacer puntos.');

        end

    end

%% =====================================================
% CANCELAR CAPTURA
% ======================================================

    function cancelarCaptura(~,~)

        if ~capturando
            return
        end

        if isempty(puntosTemporales)

            finalizarEdicion();
            return
        end

        respuesta = questdlg( ...
            ['¿Desea descartar los puntos de esta edicion?', ...
             ' El contorno guardado anteriormente se conservara.'], ...
            'Cancelar captura', ...
            'Descartar cambios', ...
            'Continuar editando', ...
            'Continuar editando');

        if strcmp(respuesta,'Descartar cambios')
            finalizarEdicion();
        end

    end

%% =====================================================
% RESTAURAR CONTROLES
% ======================================================

    function finalizarEdicion()

        capturando = false;

        indiceCaptura = 0;
        puntosTemporales = zeros(0,2);

        % Desactivar callbacks de captura.
        set(fig, ...
            'WindowButtonDownFcn',[], ...
            'WindowKeyPressFcn',[]);

        set([sel,botMarcar,botBorrar, ...
             cbTrazo,cbZoom,cbModelo,cbInicial], ...
            'Enable','on');

        set([botTerminar,botDeshacer,botCancelar], ...
            'Visible','off');

        if ~isempty(hTemporal)

            hValidos = hTemporal(isgraphics(hTemporal));

            if ~isempty(hValidos)
                delete(hValidos);
            end

        end

        hTemporal = gobjects(0);

        refrescar([],[]);

    end

%% =====================================================
% BORRAR CONTORNO GUARDADO
% ======================================================

    function borrarTrazo(~,~)

        if capturando
            return
        end

        indice = get(sel,'Value');

        hayTrazo = ~isempty(trazos{indice}) || ...
            isfile(matrices{indice});

        if ~hayTrazo

            msgbox( ...
                'No existe un contorno guardado para esta referencia.', ...
                'Sin trazo');

            return
        end

        respuesta = questdlg( ...
            sprintf([ ...
                '¿Eliminar el contorno de:\n%s?\n\n', ...
                'Esta accion borrara tambien el archivo .mat.'], ...
                nombres{indice}), ...
            'Confirmar eliminacion', ...
            'Borrar trazo', ...
            'Cancelar', ...
            'Cancelar');

        if ~strcmp(respuesta,'Borrar trazo')
            return
        end

        try

            if isfile(matrices{indice})
                delete(matrices{indice});
            end

        catch ME

            errordlg( ...
                sprintf('No se pudo borrar:\n%s',ME.message), ...
                'Error al borrar');

            return
        end

        trazos{indice} = [];

        refrescar([],[]);

    end

end


%% =====================================================
% REGISTRO MORFOLOGICO DE CONTORNOS /r/
% ======================================================

function [t,h] = registrar_contorno_r(P)
% registrar_contorno_r
%
% Registra un segmento de contorno para comparar
% su forma independientemente de su posicion,
% orientacion global y escala.
%
% ENTRADA:
%   P : Nx2, coordenadas [X Z]
%
% CONVENCION:
%   X positivo hacia posterior.
%   Z positivo hacia arriba.
%
% SALIDAS:
%   t : avance normalizado sobre el eje local
%   h : desviacion perpendicular normalizada
%
% Los resultados son adimensionales.
% No representan distancias anatomicas en mm.

%% 1. VALIDACION

P = double(P);

if size(P,2)~=2 || size(P,1)<2

    error('El contorno debe contener al menos dos puntos Nx2.');

end

if any(~isfinite(P(:)))

    error('El contorno contiene coordenadas no finitas.');

end

%% 2. ORDEN ANTERIOR A POSTERIOR

% Si los puntos fueron marcados desde posterior
% hacia anterior, invertir automaticamente
% el orden del recorrido.

if P(end,1)<P(1,1)

    P = flipud(P);

end

%% 3. TRASLACION AL ORIGEN

P = P-P(1,:);

%% 4. EJE LONGITUDINAL DEL SEGMENTO

% El eje local une el primero y ultimo punto.

v = P(end,:);

L = hypot(v(1),v(2));

if L<=1e-9

    error(['El primero y ultimo punto del contorno ', ...
           'no deben coincidir.']);

end

% Vector unitario longitudinal.
ex = v/L;

% Vector unitario perpendicular.
% Su componente positiva representa elevacion
% respecto al eje longitudinal local.

ez = [-ex(2),ex(1)];

%% 5. PROYECCION SOBRE LOS EJES LOCALES

longitudinal = P*ex';
transversal = P*ez';

%% 6. NORMALIZACION

% Se emplea una misma longitud para los dos ejes.
% Esto conserva las proporciones de la curva.

t = longitudinal/L;
h = transversal/L;

% Evitar pequenas desviaciones numericas
% en los extremos.

t(1) = 0;
t(end) = 1;

h(1) = 0;
h(end) = 0;

end
