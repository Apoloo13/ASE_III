clear;
clc;
close all;

%% ============================================================
% SELECCIONAR ARCHIVO EXCEL
% ============================================================

[nombreArchivo, rutaArchivo] = uigetfile( ...
    {'*.xlsx;*.xls','Archivos de Excel (*.xlsx, *.xls)'}, ...
    'Selecciona el archivo exportado desde CATIA');

if isequal(nombreArchivo,0)
    error('No se selecciono ningun archivo.');
end

archivo = fullfile(rutaArchivo,nombreArchivo);


%% ============================================================
% LEER SOLO LAS COLUMNAS A:E
%
% A = Punto
% B = S_mm
% C = X_mm
% D = Y_mm
% E = Z_mm
% ============================================================

datos = readmatrix(archivo,'Range','A:E');


%% ============================================================
% EXTRAER COLUMNAS
% ============================================================

Punto = datos(:,1);
S     = datos(:,2);
X     = datos(:,3);
Y     = datos(:,4);
Z     = datos(:,5);


%% ============================================================
% ELIMINAR FILAS VACIAS O INVALIDAS
% ============================================================

validos = ...
    isfinite(S) & ...
    isfinite(X) & ...
    isfinite(Y) & ...
    isfinite(Z);

Punto = Punto(validos);
S = S(validos);
X = X(validos);
Y = Y(validos);
Z = Z(validos);


%% ============================================================
% ORDENAR LOS DATOS SEGUN S
% ============================================================

[S, indice] = sort(S);

Punto = Punto(indice);
X = X(indice);
Y = Y(indice);
Z = Z(indice);


%% ============================================================
% ELIMINAR VALORES REPETIDOS DE S
% ============================================================

[S, indiceUnico] = unique(S,'stable');

Punto = Punto(indiceUnico);
X = X(indiceUnico);
Y = Y(indiceUnico);
Z = Z(indiceUnico);


%% ============================================================
% MOSTRAR DATOS LEIDOS
% ============================================================

fprintf('\n');
fprintf('========================================\n');
fprintf(' DATOS LEIDOS DESDE CATIA\n');
fprintf('========================================\n');

fprintf('Numero de puntos: %d\n',length(S));
fprintf('S inicial: %.6f mm\n',S(1));
fprintf('S final: %.6f mm\n',S(end));

fprintf('========================================\n\n');


%% ============================================================
% MOSTRAR PRIMEROS PUNTOS
% ============================================================

nMostrar = min(10,length(S));

fprintf('Primeros puntos:\n\n');

fprintf(' Punto        S           X           Y           Z\n');
fprintf('--------------------------------------------------------\n');

for i = 1:nMostrar

    fprintf('%5.0f   %10.3f  %10.3f  %10.3f  %10.3f\n', ...
        Punto(i),S(i),X(i),Y(i),Z(i));

end


%% ============================================================
% GRAFICAR LOS PUNTOS ORIGINALES
% ============================================================

figure;

plot3(X,Y,Z,'o');

grid on;
axis equal;

xlabel('X [mm]');
ylabel('Y [mm]');
zlabel('Z [mm]');

title('Puntos originales exportados desde CATIA');

view(3);

rotate3d on;


%% ============================================================
% CREAR PARAMETRO NORMALIZADO t
%
% t = 0 -> inicio de trayectoria
% t = 1 -> final de trayectoria
% ============================================================

t = (S - S(1)) / (S(end) - S(1));


%% ============================================================
% CREAR SPLINES CUBICAS
%
% X = X(t)
% Y = Y(t)
% Z = Z(t)
% ============================================================

ppX = spline(t,X);
ppY = spline(t,Y);
ppZ = spline(t,Z);


%% ============================================================
% CREAR CURVA SUAVE
% ============================================================

tf = linspace(0,1,2000);

Xf = ppval(ppX,tf);
Yf = ppval(ppY,tf);
Zf = ppval(ppZ,tf);


%% ============================================================
% GRAFICAR PUNTOS + SPLINE
% ============================================================

figure;

plot3(X,Y,Z,'o');

hold on;

plot3(Xf,Yf,Zf,'LineWidth',1.5);

grid on;
axis equal;

xlabel('X [mm]');
ylabel('Y [mm]');
zlabel('Z [mm]');

title('Trayectoria 3D reconstruida');

legend( ...
    'Puntos de CATIA', ...
    'Spline de MATLAB', ...
    'Location','best');

view(3);

rotate3d on;


%% ============================================================
% CALCULAR ERROR DE INTERPOLACION
% ============================================================

Xcalc = ppval(ppX,t);
Ycalc = ppval(ppY,t);
Zcalc = ppval(ppZ,t);

error3D = sqrt( ...
    (X-Xcalc).^2 + ...
    (Y-Ycalc).^2 + ...
    (Z-Zcalc).^2);


fprintf('\n');
fprintf('========================================\n');
fprintf(' ERROR DE INTERPOLACION\n');
fprintf('========================================\n');

fprintf('Error maximo:   %.12f mm\n',max(error3D));
fprintf('Error promedio: %.12f mm\n',mean(error3D));

fprintf('========================================\n\n');


%% ============================================================
% POSICION PARA UN VALOR DE t
% ============================================================

tPrueba = 0.5;

xPrueba = ppval(ppX,tPrueba);
yPrueba = ppval(ppY,tPrueba);
zPrueba = ppval(ppZ,tPrueba);


fprintf('========================================\n');
fprintf(' POSICION EN t = %.3f\n',tPrueba);
fprintf('========================================\n');

fprintf('X = %.6f mm\n',xPrueba);
fprintf('Y = %.6f mm\n',yPrueba);
fprintf('Z = %.6f mm\n',zPrueba);

fprintf('========================================\n\n');


%% ============================================================
% OBTENER COEFICIENTES DE LAS SPLINES
% ============================================================

[breaksX,coefX] = unmkpp(ppX);
[breaksY,coefY] = unmkpp(ppY);
[breaksZ,coefZ] = unmkpp(ppZ);


%% ============================================================
% MOSTRAR ECUACIONES POR SEGMENTOS
% ============================================================

fprintf('========================================\n');
fprintf(' ECUACIONES PARAMETRICAS POR SEGMENTOS\n');
fprintf('========================================\n\n');


for i = 1:size(coefX,1)

    fprintf('----------------------------------------\n');
    fprintf('SEGMENTO %d\n',i);
    fprintf('%.8f <= t <= %.8f\n\n', ...
        breaksX(i),breaksX(i+1));

    fprintf('u = t - %.12f\n\n',breaksX(i));

    fprintf( ...
        'X(u) = %.12f*u^3 + %.12f*u^2 + %.12f*u + %.12f\n', ...
        coefX(i,1),coefX(i,2),coefX(i,3),coefX(i,4));

    fprintf( ...
        'Y(u) = %.12f*u^3 + %.12f*u^2 + %.12f*u + %.12f\n', ...
        coefY(i,1),coefY(i,2),coefY(i,3),coefY(i,4));

    fprintf( ...
        'Z(u) = %.12f*u^3 + %.12f*u^2 + %.12f*u + %.12f\n\n', ...
        coefZ(i,1),coefZ(i,2),coefZ(i,3),coefZ(i,4));

end


%% ============================================================
% ANIMACION
% ============================================================

figure;

plot3(Xf,Yf,Zf,'LineWidth',1.5);

hold on;

puntoAnimado = plot3( ...
    Xf(1),Yf(1),Zf(1), ...
    'o', ...
    'MarkerSize',10);

grid on;
axis equal;

xlabel('X [mm]');
ylabel('Y [mm]');
zlabel('Z [mm]');

title('Movimiento sobre la trayectoria');

view(3);


for i = 1:5:length(tf)

    set( ...
        puntoAnimado, ...
        'XData',Xf(i), ...
        'YData',Yf(i), ...
        'ZData',Zf(i));

    drawnow;

end


%% ============================================================
% FIN
% ============================================================

disp(' ');
disp('Proceso terminado correctamente.');