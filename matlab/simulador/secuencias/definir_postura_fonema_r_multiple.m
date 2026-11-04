
function postura = definir_postura_fonema_r_multiple(sistema)
% DEFINIR_POSTURA_FONEMA_R_MULTIPLE
%
% Configuracion pre-vibratoria /r/: candidata R16.
%
% Derivada de la exploracion R8-R12 y del
% refinamiento local R13-R17.
%
% Registro de referencia: Y +3 mm, Z +1 mm.
%
% No modela vibracion, flujo aerodinamico ni
% contacto tridimensional electropalatografico.
%
% No modifica la cavidad ni parametros FEM.

%% 1. REFERENCIA FEM

M = sistema.malla;
X0 = M.nodos;

idPunta = M.seguimiento.puntaIndice;
punta0 = X0(idPunta,:);

% El mismo registro utilizado en las pruebas.
assert(norm(punta0-[3 1])<1e-6, ...
    ['La postura R16 requiere la referencia ', ...
     'lingual Y=+3 mm, Z=+1 mm.']);

ids = M.frontera.superior(:);

L = punta0(1)-min(X0(:,1));

assert(L>0,'Longitud de referencia invalida.');

s = (punta0(1)-X0(ids,1))/L;

[s,orden] = sort(s);
ids = ids(orden);

[s,iu] = unique(s,'stable');
ids = ids(iu);

P0 = X0(ids,:);

%% 2. PARAMETROS GEOMETRICOS R16

% Coordenadas materiales de control.
sControl = [
    0.035
    0.085
    0.16
    0.28
    0.55
    0.82
];

pesos = [
    0.90
    0.70
    0.48
    0.28
    0.18
    0.12
];

Pini = interp1(s,P0,sControl,'linear');

assert(all(isfinite(Pini(:))), ...
    'No se pudieron interpolar los objetivos.');

%% 3. REFERENCIA ALVEOLAR

R = sistema.contactoSagital.regiones;

indiceAlveolar = find(strcmpi( ...
    string({R.nombre}),'Alveolar'),1);

assert(~isempty(indiceAlveolar), ...
    'No se encontro la region alveolar.');

B = R(indiceAlveolar);

ok = B.valido(:) & ...
    isfinite(B.y(:)) & ...
    isfinite(B.zSuperior(:));

A = sortrows( ...
    [B.y(ok),B.zSuperior(ok)],1);

[~,iu] = unique(A(:,1),'stable');
A = A(iu,:);

assert(size(A,1)>=3, ...
    'Contorno alveolar insuficiente.');

%% 4. OBJETIVO APICAL ORIGINAL

% Objetivo teorico utilizado en R8-R12.
% Se calcula desde la superficie alveolar real.

yA = A(1,1)+0.60*(A(end,1)-A(1,1));

zA = interp1( ...
    A(:,1),A(:,2),yA,'linear');

separacionObjetivo = 0.40;

puntaMeta = [
    yA, zA-separacionObjetivo
];

Delta = puntaMeta-punta0;

%% 5. DISTRIBUCION DE MOVIMIENTO R12

% Amplitudes de R12.
fTip = 1.00;
fAnt = 0.60;
fPost = 0.50;

% Acompanamiento apical y laminal.
dAnterior = [
    0.90*Delta(1), 0.83*Delta(2)
    0.70*Delta(1), 0.67*Delta(2)
    0.40*Delta(1), 0.48*Delta(2)
    0.22*Delta(1), 0.30*Delta(2)
    0.10*Delta(1), 0.10*Delta(2)
    0.00,          0.025*Delta(2)
];

% Elevacion adicional del dorso.
dElevacionDorsal = [
    0.00  0.00
    0.00  0.10
    0.00  0.40
    0.00  0.65
    0.00  0.30
    0.00  0.10
];

% Ajuste posterior exploratorio.
dPosterior = [
     0.00  0.00
     0.00  0.00
     0.00  0.00
     0.00  0.00
    -0.25  0.00
    -0.60 -0.10
];

objetivos = Pini + ...
    fTip*dAnterior + ...
    fAnt*dElevacionDorsal + ...
    fPost*dPosterior;

puntaFinal = punta0+fTip*Delta;

%% 6. REFINAMIENTO R16

% R16: desplazamiento anterior de +0.12 mm.
% Se aplica un acompanamiento reducido
% a los dos primeros objetivos dorsales.

ajusteY = 0.12;

puntaFinal(1) = puntaFinal(1)+ajusteY;

objetivos(1,1) = ...
    objetivos(1,1)+0.65*ajusteY;

objetivos(2,1) = ...
    objetivos(2,1)+0.25*ajusteY;

%% 7. CONFIGURACION DEFINITIVA

postura = struct();

postura.nombre = ...
    "Fonema /r/ - postura pre-vibratoria R16";

postura.puntaYZ = puntaFinal;

postura.dorso = [
    sControl objetivos pesos
];

postura.vientre = zeros(0,4);

postura.anguloApice = NaN;
postura.anguloLamina = NaN;

postura.curvaturaApical = 0;
postura.curvaturaLaminal = 0;

end