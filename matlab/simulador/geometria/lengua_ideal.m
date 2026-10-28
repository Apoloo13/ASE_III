function lengua = lengua_ideal(parametros, ax3D, axSagital)
% Modelo parametrico con 9 costillas y punta continua.
% Coordenadas relativas a la punta en reposo.

% 1. PARAMETROS
if nargin < 1 || isempty(parametros)
    parametros = struct();
end
if nargin < 2, ax3D = []; end
if nargin < 3, axSagital = []; end

if ~isfield(parametros,'dzCostillas')
    parametros.dzCostillas = zeros(1,9);
end
if ~isfield(parametros,'dzPunta')
    parametros.dzPunta = 0;
end
if ~isfield(parametros,'puntaReposo')
    parametros.puntaReposo = [0 23.5 -1.15];
end
if ~isfield(parametros,'desplazamientoGlobal')
    parametros.desplazamientoGlobal = [0 0 0];
end

validateattributes(parametros.dzCostillas,{'numeric'}, ...
    {'vector','numel',9,'finite'});

validateattributes(parametros.dzPunta,{'numeric'}, ...
    {'scalar','finite'});

validateattributes(parametros.puntaReposo,{'numeric'}, ...
    {'vector','numel',3,'finite'});

validateattributes(parametros.desplazamientoGlobal,{'numeric'}, ...
    {'vector','numel',3,'finite'});

movCostillas = reshape(parametros.dzCostillas,1,[]);
puntaReposo = reshape(parametros.puntaReposo,1,[]);
desplazamiento = reshape(parametros.desplazamientoGlobal,1,[]);

% 2. GEOMETRIA DE REFERENCIA

% Distribucion uniforme de las 9 costillas.
% Se extiende hacia la zona posterior sin desplazar la punta.
nCostillas = 9;
yInicioCostillas = -28;
yFinCostillas = 21;

yCostillas = linspace(yInicioCostillas, yFinCostillas, nCostillas);

% Perfiles verticales originales
zSuperior = [6.2 7.0 8.2 9.0 9.3 8.9 8.0 6.8 5.5];
zInferior = [2.2 2.3 2.4 2.5 2.6 2.5 2.4 2.3 2.2];

% Ampliacion transversal de la lengua
factorAncho = 1.28;

semiancho = factorAncho * ...
    [8.5 9.8 11.0 12.0 12.5 12.0 10.8 9.0 7.2];

desplazamientoInicialZ = -5.0;
longitudPunta = 2.5;
potenciaTransversal = 0.65;

% Resolucion adaptada a la nueva longitud
nLongitud = 260;
nPunta = 45;
nAngular = 101;

% Distribucion longitudinal del cuerpo y punto auxiliar posterior
yControl = [yCostillas(1)-2, yCostillas];

% Perfiles de altura y anchura
zControlSup = [5.8, zSuperior + movCostillas] ...
    + desplazamientoInicialZ;

zControlInf = [2.1, zInferior + movCostillas] ...
    + desplazamientoInicialZ;

anchoControl = [8.0*factorAncho, semiancho];

% Interpolacion continua entre las nueve costillas
yCuerpo = linspace(yControl(1), yControl(end), nLongitud);

zSupCuerpo = interp1(yControl, zControlSup, ...
    yCuerpo, 'pchip');

zInfCuerpo = interp1(yControl, zControlInf, ...
    yCuerpo, 'pchip');

wCuerpo = interp1(yControl, anchoControl, ...
    yCuerpo, 'pchip');


% 3. PUNTA CONTINUA
yUnion = yCostillas(end);
yExtremo = yUnion + longitudPunta;

zSupUnion = zSupCuerpo(end);
zInfUnion = zInfCuerpo(end);
wUnion = wCuerpo(end);

zExtremo = (zSupUnion + zInfUnion)/2 + parametros.dzPunta;

pasoDerivada = 0.01;

pendSup = (zSupUnion - interp1(yControl,zControlSup, ...
    yUnion-pasoDerivada,'pchip'))/pasoDerivada;

pendInf = (zInfUnion - interp1(yControl,zControlInf, ...
    yUnion-pasoDerivada,'pchip'))/pasoDerivada;

pendAncho = (wUnion - interp1(yControl,anchoControl, ...
    yUnion-pasoDerivada,'pchip'))/pasoDerivada;

t = linspace(0,1,nPunta+1);
t = t(2:end);

yRedondeo = yUnion + longitudPunta*t;

f = sqrt(max(0,1-t.^2));
g = longitudPunta*t.*(1-t).^2;

zSupRedondeo = zExtremo + (zSupUnion-zExtremo)*f + pendSup*g;
zInfRedondeo = zExtremo + (zInfUnion-zExtremo)*f + pendInf*g;
wRedondeo = wUnion*f + pendAncho*g;

yOriginal = [yCuerpo,yRedondeo];
zSupOriginal = [zSupCuerpo,zSupRedondeo];
zInfOriginal = [zInfCuerpo,zInfRedondeo];
wOriginal = [wCuerpo,wRedondeo];

if any(zSupOriginal(1:end-1) <= zInfOriginal(1:end-1)) || ...
        any(wOriginal(1:end-1) <= 0)
    error('Geometria lingual invalida. Revisa los controles.');
end

% 4. SUPERFICIE TRIDIMENSIONAL
angulo = linspace(0,2*pi,nAngular)';

perfilVertical = sign(sin(angulo)) .* ...
    abs(sin(angulo)).^potenciaTransversal;

zCentral = (zSupOriginal+zInfOriginal)/2;
semiespesor = (zSupOriginal-zInfOriginal)/2;

X = cos(angulo)*wOriginal ...
    - puntaReposo(1) + desplazamiento(1);

Y = ones(nAngular,1)*yOriginal ...
    - puntaReposo(2) + desplazamiento(2);

Z = ones(nAngular,1)*zCentral ...
    + perfilVertical*semiespesor ...
    - puntaReposo(3) + desplazamiento(3);

% 5. PERFIL SAGITAL Y PUNTOS DE CONTROL
ySagital = yOriginal ...
    - puntaReposo(2) + desplazamiento(2);

zSagitalSuperior = zSupOriginal ...
    - puntaReposo(3) + desplazamiento(3);

zSagitalInferior = zInfOriginal ...
    - puntaReposo(3) + desplazamiento(3);

punta = [0,yExtremo,zExtremo] ...
    - puntaReposo + desplazamiento;

centrosCostillas = [ ...
    zeros(9,1), ...
    yCostillas(:), ...
    zSuperior(:)+movCostillas(:)+desplazamientoInicialZ ...
    ] - puntaReposo + desplazamiento;

% 6. DATOS DE SALIDA
lengua.malla.X = X;
lengua.malla.Y = Y;
lengua.malla.Z = Z;

lengua.sagital.y = ySagital;
lengua.sagital.zSuperior = zSagitalSuperior;
lengua.sagital.zInferior = zSagitalInferior;

lengua.costillas.centros = centrosCostillas;
lengua.costillas.desplazamientos = movCostillas;

lengua.punta = punta;
lengua.parametros = parametros;

lengua.graficos = struct( ...
    'superficie3D',[], ...
    'cierrePosterior',[], ...
    'lineasCostillas',[], ...
    'puntosCostillas',[], ...
    'punta3D',[], ...
    'sombraSagital',[], ...
    'perfilSuperior',[], ...
    'perfilInferior',[], ...
    'puntosSagitales',[], ...
    'puntaSagital',[]);

% 7. VISUALIZACION 3D
if ~isempty(ax3D)

    if ~isgraphics(ax3D,'axes')
        error('ax3D no es un eje valido.');
    end

    hold(ax3D,'on');

    lengua.graficos.superficie3D = surf(ax3D,X,Y,Z, ...
        'FaceColor',[0.83 0.45 0.55], ...
        'FaceAlpha',0.92, ...
        'EdgeColor','none', ...
        'DisplayName','Lengua ideal');

    lengua.graficos.cierrePosterior = fill3(ax3D, ...
        X(:,1),Y(:,1),Z(:,1),[0.76 0.36 0.46], ...
        'FaceAlpha',0.87, ...
        'EdgeColor','none', ...
        'HandleVisibility','off');

    anguloCostilla = linspace(0,pi,80);

    lineas = gobjects(9,1);
    puntos = gobjects(9,1);

    for i = 1:9

        zSup = zSuperior(i)+movCostillas(i) ...
            + desplazamientoInicialZ;

        zInf = zInferior(i)+movCostillas(i) ...
            + desplazamientoInicialZ;

        zMed = (zSup+zInf)/2;
        espesorMedio = (zSup-zInf)/2;

        xc = semiancho(i)*cos(anguloCostilla) ...
            - puntaReposo(1)+desplazamiento(1);

        yc = (yCostillas(i)-puntaReposo(2) ...
            + desplazamiento(2))*ones(size(anguloCostilla));

        zc = zMed + espesorMedio * ...
            sin(anguloCostilla).^potenciaTransversal ...
            - puntaReposo(3)+desplazamiento(3)+0.06;

        lineas(i) = plot3(ax3D,xc,yc,zc,':', ...
            'Color',[0.65 0.48 0.53], ...
            'LineWidth',0.65, ...
            'HandleVisibility','off');

        puntos(i) = plot3(ax3D, ...
            centrosCostillas(i,1), ...
            centrosCostillas(i,2), ...
            centrosCostillas(i,3)+0.08,'o', ...
            'MarkerSize',5, ...
            'MarkerFaceColor',[1 0.9 0.2], ...
            'MarkerEdgeColor',[0.45 0.34 0.28], ...
            'HandleVisibility','off');

    end

    lengua.graficos.lineasCostillas = lineas;
    lengua.graficos.puntosCostillas = puntos;

    lengua.graficos.punta3D = plot3(ax3D, ...
        punta(1),punta(2),punta(3),'o', ...
        'MarkerSize',8, ...
        'MarkerFaceColor',[0.95 0.15 0.17], ...
        'MarkerEdgeColor',[0.7 0.1 0.12], ...
        'HandleVisibility','off');

end

% 8. VISUALIZACION SAGITAL
if ~isempty(axSagital)

    if ~isgraphics(axSagital,'axes')
        error('axSagital no es un eje valido.');
    end

    hold(axSagital,'on');

    lengua.graficos.sombraSagital = fill(axSagital, ...
        [ySagital,fliplr(ySagital)], ...
        [zSagitalSuperior,fliplr(zSagitalInferior)], ...
        [0.91 0.66 0.72], ...
        'FaceAlpha',0.40, ...
        'EdgeColor','none', ...
        'HandleVisibility','off');

    lengua.graficos.perfilSuperior = plot(axSagital, ...
        ySagital,zSagitalSuperior, ...
        'Color',[0.85 0.13 0.22], ...
        'LineWidth',2.0, ...
        'DisplayName','Dorso lingual');

    lengua.graficos.perfilInferior = plot(axSagital, ...
        ySagital,zSagitalInferior, ...
        'Color',[0.65 0.25 0.45], ...
        'LineWidth',1.4, ...
        'HandleVisibility','off');

    lengua.graficos.puntosSagitales = plot(axSagital, ...
        centrosCostillas(:,2), ...
        centrosCostillas(:,3),'o', ...
        'MarkerSize',5, ...
        'MarkerFaceColor',[1 0.9 0.2], ...
        'MarkerEdgeColor',[0.45 0.34 0.28], ...
        'HandleVisibility','off');

    lengua.graficos.puntaSagital = plot(axSagital, ...
        punta(2),punta(3),'o', ...
        'MarkerSize',8, ...
        'MarkerFaceColor',[0.95 0.15 0.17], ...
        'MarkerEdgeColor',[0.7 0.1 0.12], ...
        'HandleVisibility','off');

    set(axSagital,'XDir','reverse','YDir','normal');
    axis(axSagital,'equal');

end

end