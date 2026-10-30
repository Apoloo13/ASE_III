
function reporte = analizar_correspondencia_comun( ...
    sistema,simulacion,fonema)
% ANALIZAR_CORRESPONDENCIA_COMUN
%
% Evaluacion sagital comparable entre fonemas.
%
% Para cada region material y anatomica calcula:
% - Distancia minima a ambas envolventes STL.
% - Holgura vertical respecto al borde inferior.
% - Solapamiento longitudinal en Y.
% - Longitud proxima al borde inferior.
% - Longitud dentro de la franja regional.
%
% La entrada en la franja NO demuestra contacto.
% No modifica la geometria ni el FEM.
%
% Unidades: mm.

%% 1. DATOS MATERIALES

malla = sistema.malla;
X0 = malla.nodos;

ids = malla.frontera.superior(:);

yp = X0(malla.seguimiento.puntaIndice,1);
L = yp-min(X0(:,1));

s = (yp-X0(ids,1))/L;

[s,orden] = sort(s);
ids = ids(orden);

P = simulacion.estado.nodos(ids,:);

%% 2. REGIONES FUNCIONALES COMUNES

grupos = [
    0.00 0.12
    0.12 0.32
    0.16 0.28
];

nombres = {
    'Apice'
    'Lamina'
    'Lamina central'
};

regiones = sistema.contactoSagital.regiones;

umbralProximo = 1.0;

reporte = struct([]);

%% 3. EVALUACION

fprintf('\n===== CORRESPONDENCIA COMUN: %s =====\n', ...
    fonema);

fprintf(['%-15s %-11s %8s %8s ', ...
    '%8s %8s %8s %8s\n'], ...
    'Material','Region','D.Inf','D.Sup', ...
    'GapY','HolgMin','L.Cerca','L.Zona');

n = 0;

for i = 1:size(grupos,1)

    sEval = linspace( ...
        grupos(i,1),grupos(i,2),301)';

    Q = interp1(s,P,sEval,'linear');

    longitudes = hypot( ...
        diff(Q(:,1)),diff(Q(:,2)));

    for j = 1:numel(regiones)

        R = regiones(j);

        if ~any(strcmpi(string(R.nombre), ...
                ["Dental","Alveolar"]))
            continue
        end

        validos = R.valido(:) & ...
            isfinite(R.y(:)) & ...
            isfinite(R.zInferior(:)) & ...
            isfinite(R.zSuperior(:));

        yR = R.y(validos);
        zInf = R.zInferior(validos);
        zSup = R.zSuperior(validos);

        [yR,ord] = sort(yR);

        zInf = zInf(ord);
        zSup = zSup(ord);

        [yR,iu] = unique(yR,'stable');

        zInf = zInf(iu);
        zSup = zSup(iu);

        if numel(yR)<2
            continue
        end

        %% DISTANCIAS EUCLIDIANAS

        Dinf = hypot( ...
            Q(:,1)-yR',Q(:,2)-zInf');

        Dsup = hypot( ...
            Q(:,1)-yR',Q(:,2)-zSup');

        [dInf,idx] = min(Dinf(:));
        dSup = min(Dsup(:));

        [iP,~] = ind2sub(size(Dinf),idx);

        sCercano = sEval(iP);

        %% CORRESPONDENCIA EN Y

        gapY = max(0, ...
            max(min(yR)-max(Q(:,1)), ...
                min(Q(:,1))-max(yR)));

        %% HOLGURA VERTICAL

        zi = interp1( ...
            yR,zInf,Q(:,1),'linear',NaN);

        zs = interp1( ...
            yR,zSup,Q(:,1),'linear',NaN);

        validoY = isfinite(zi) & isfinite(zs);

        h = zi-Q(:,2);

        if any(validoY)
            hMin = min(h(validoY));
        else
            hMin = NaN;
        end

        %% PROXIMIDAD AL BORDE INFERIOR

        cerca = validoY & ...
            h>=0 & h<=umbralProximo;

        longitudCerca = sum(longitudes( ...
            cerca(1:end-1) & cerca(2:end)));

        %% OCUPACION DE LA FRANJA REGIONAL

        % Indicador de correspondencia espacial.
        % No equivale a contacto anatomico valido.

        dentro = validoY & ...
            Q(:,2)>=zi & Q(:,2)<=zs;

        longitudZona = sum(longitudes( ...
            dentro(1:end-1) & dentro(2:end)));

        %% GUARDAR RESULTADOS

        n = n+1;

        reporte(n).fonema = fonema;
        reporte(n).material = nombres{i};
        reporte(n).region = char(R.nombre);

        reporte(n).dInferior_mm = dInf;
        reporte(n).dSuperior_mm = dSup;

        reporte(n).gapY_mm = gapY;
        reporte(n).holguraMin_mm = hMin;

        reporte(n).longitudCerca_mm = longitudCerca;
        reporte(n).longitudZona_mm = longitudZona;

        reporte(n).sCercano = sCercano;

        fprintf(['%-15s %-11s %8.3f %8.3f ', ...
            '%8.3f %8.3f %8.3f %8.3f\n'], ...
            nombres{i},char(R.nombre), ...
            dInf,dSup,gapY,hMin, ...
            longitudCerca,longitudZona);

    end

end

%% 4. RESUMEN MECANICO

fprintf('\n===== FEM: %s =====\n',fonema);

fprintf('GreenMax: %.4f\n', ...
    simulacion.resumen.GreenMax);

fprintf('Jmin: %.4f\n', ...
    simulacion.resumen.Jmin);

fprintf('Jmax: %.4f\n', ...
    simulacion.validacion.global.Jmax);

fprintf('Cumple FEM: %d\n', ...
    simulacion.resumen.cumpleCriteriosExploratorios);

fprintf(['L.Zona indica entrada en la franja ', ...
    'STL, no contacto fisico validado.\n']);

end
