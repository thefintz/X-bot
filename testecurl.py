import requests
import json

url = "https://www.rad.cvm.gov.br/ENET/frmConsultaExternaCVM.aspx/ListarDocumentos"
headers = {
    "Content-Type": "application/json; charset=utf-8",
    "X-Requested-With": "XMLHttpRequest"
}

#  parametros que sao passados p requisicao. alguns desnecessarios foram removidos. ou seja sao os filtros la da cvm
data = {
    "dataDe": "",
    "dataAte": "",
    "empresa": "",
    "setorAtividade": "-1",
    "categoriaEmissor": "-1",
    "situacaoEmissor": "-1",
    "tipoParticipante": "1,2,8",
    "dataReferencia": "",
    "categoria": "IPE_3_84_-1",  # categoria p "aviso aos acionistas" + "outros avisos"
    "periodo": "1",   # esse 1 q define perido, nesse caso (1) para semana
    "horaIni": "",
    "horaFim": "",
    "palavraChave": "",
    "ultimaDtRef": "false",
    "tipoEmpresa": "1",
    "token": "",
    "versaoCaptcha": ""
}

# fazemos a requisicao post com cabecalho e os filtros
response = requests.post(url, headers=headers, json=data)

# salva a resposta em um json
with open("response.json", "w") as outfile: # so nomeia com outfile, converte o request.post em dic, especifica onde vai ser gravado...
    json.dump(response.json(), outfile, ensure_ascii=False, indent=4) # ... nn tira acentos e identa em 4 p ficar melhor leitura 
