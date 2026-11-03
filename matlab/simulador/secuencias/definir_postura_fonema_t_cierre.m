
function postura = definir_postura_fonema_t_cierre(sistema)
% DEFINIR_POSTURA_FONEMA_T_CIERRE
% Postura /t/ T5, factor 0.83, con referencia Z +1 mm.
% Reproduce la configuracion seleccionada en las pruebas.
% No modifica la cavidad, la malla ni el modelo biomecanico.

%% 1. REFERENCIA FEM

M = sistema.malla;
X0 = M.nodos;

ids = M.frontera.superior(:);

idPunta = M.seguimiento.puntaIndice;
punta0 = X0(idPunta,:);

L = punta0(1)-min(X0(:,1));

s = (punta0(1)-X0(ids,1))/L;

[s,orden] = sort(s);
ids = ids(orden);

[s,iu] = unique(s,'stable');
ids = ids(iu);

P0 = X0(ids,:);

%% 2. PARAMETROS DE LA POSTURA

factor = 0.83;

% Esta referencia debe prepararse con [0 3 1].
registroZ = 1.00;

assert(norm(punta0-[3 registroZ])<1e-6, ...
    ['La postura /t/ requiere la referencia ', ...
     'lingual Y=+3 mm y Z=+1 mm.']);

sControl = [0.04;0.08;0.12;0.18;0.26];

pesos = [0.85;0.90;0.65;0.35;0.15];

Pini = interp1(s,P0,sControl,'linear');

%% 3. CONTORNOS ANATOMICOS

R = sistema.contactoSagital.regiones;
nombres = string({R.nombre});

iDental = find(strcmpi(nombres,'Dental'),1);
iAlveolar = find(strcmpi(nombres,'Alveolar'),1);

assert(~isempty(iDental) && ~isempty(iAlveolar), ...
    'Faltan las regiones dental y alveolar.');

D = contorno_superior(R(iDental));
A = contorno_superior(R(iAlveolar));

%% 4. OBJETIVOS T5 ORIGINALES

yTip = 5.50;

zTip = interp1(D(:,1),D(:,2), ...
    yTip,'linear',NaN);

y1 = 4.00;
y2 = 2.50;

z1 = interp1(A(:,1),A(:,2), ...
    y1,'linear',NaN);

z2 = interp1(A(:,1),A(:,2), ...
    y2,'linear',NaN);

assert(all(isfinite([zTip z1 z2])), ...
    'No se pudieron definir los objetivos anatomicos.');

% La correccion Z es rigida y se aplica tambien
% a los objetivos absolutos del modelo original.

puntaMeta = [ ...
    yTip, zTip-0.65+registroZ];

Pmeta = [
    y1,              z1-0.25+registroZ
    y2,              z2-0.65+registroZ
    0.00,            Pini(3,2)+1.70
    Pini(4,1)+1.00,  Pini(4,2)+0.50
    Pini(5,1)+0.25,  Pini(5,2)+0.10
];

%% 5. CONFIGURACION FINAL

postura = struct();

postura.nombre = ...
    "Fonema /t/ - cierre apico-dentoalveolar T5";

postura.puntaYZ = ...
    punta0+factor*(puntaMeta-punta0);

objetivos = Pini+factor*(Pmeta-Pini);

postura.dorso = [ ...
    sControl, objetivos, pesos];

postura.vientre = zeros(0,4);

postura.anguloApice = NaN;
postura.anguloLamina = NaN;

postura.curvaturaApical = 0;
postura.curvaturaLaminal = 0;

end

%% FUNCION AUXILIAR

function C = contorno_superior(R)

ok = R.valido(:) & ...
    isfinite(R.y(:)) & ...
    isfinite(R.zSuperior(:));

C = sortrows( ...
    [R.y(ok),R.zSuperior(ok)],1);

[~,iu] = unique(C(:,1),'stable');
C = C(iu,:);

assert(size(C,1)>=2, ...
    'Contorno superior insuficiente.');

end
