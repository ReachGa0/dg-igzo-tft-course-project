* IGZO-only M00 behavioral translation candidate R03 portable
* M01_EXECUTION_REQUIRED: not executed or simulator-validated in this revision.
* This is not native HSPICE Level 61 and is not a physical parameter card.
* Formal fitted domain: VDS=0..0.2 V, L=8..12 um, 300 K, ideal contacts.
.subckt IGZO_DG_BEHAVIORAL_R03_PORTABLE D TG BG S params: WUM=60 LUM=10
.param M00_LOGBETA=-2.714306573073809
.param M00_VTHDG=-0.01927992032790904
.param M00_ETA=0.5625448525612822
.param M00_SOFT=0.04494641359747736
.param M00_GAMMA=1.734644192947173
.param M00_KD=1.245313399341948
.param M00_LAMBDA=1.633254178584633e-33
.param M00_LOGGMIN=-29.99103683657538
.param M00_KVTHL=-0.04180975787015793
.func M00_Q(x,s) {s*ln(1+exp(min(max(x/s,-60),60)))}
BIDS D S I={sgn(V(D,S))*WUM*1e-4*(pow(10,M00_LOGBETA)*(10/LUM)*(pow(M00_Q(M00_ETA*(V(TG,S)+V(BG,S))-M00_VTHDG-M00_KVTHL*ln(LUM/10),M00_SOFT),M00_GAMMA)-pow(M00_Q(M00_ETA*(V(TG,S)+V(BG,S))-M00_VTHDG-M00_KVTHL*ln(LUM/10)-M00_KD*abs(V(D,S)),M00_SOFT),M00_GAMMA))*(1+M00_LAMBDA*abs(V(D,S)))+pow(10,M00_LOGGMIN)*abs(V(D,S)))}
.ends IGZO_DG_BEHAVIORAL_R03_PORTABLE
