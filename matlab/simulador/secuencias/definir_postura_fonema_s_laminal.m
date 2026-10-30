
function postura = definir_postura_fonema_s_laminal(sistema)
% Referencia experimental /s/ laminal S2.
% Reproduce la S2 original con registro +3 mm.
% No aplica ajustes al FEM ni a los STL.

M = sistema.malla;
X0 = M.nodos;

ids = M.frontera.superior(:);

yp = X0(M.seguimiento.puntaIndice,1);
L = yp-min(X0(:,1));

s = (yp-X0(ids,1))/L;

[s,orden] = sort(s);
ids = ids(orden);

[s,iu] = unique(s,'stable');
ids = ids(iu);

P0 = X0(ids,:);

sControl = [0.16;0.24];
Pini = interp1(s,P0,sControl,'linear');

deltaAprox = [
    3.0 2.0
    2.0 1.0
    ];

deltaFuerte = [
    6.0 3.0
    3.0 1.5
    ];

alpha = 0.45;

delta = deltaAprox + ...
    alpha*(deltaFuerte-deltaAprox);

postura = struct();

postura.nombre = "Referencia /s/ laminal S2";
postura.puntaYZ = [6 0];

postura.dorso = [
    sControl Pini+delta [0.85;0.50]
    ];

postura.vientre = zeros(0,4);

postura.anguloApice = NaN;
postura.anguloLamina = NaN;

postura.curvaturaApical = 0;
postura.curvaturaLaminal = 0;

end
