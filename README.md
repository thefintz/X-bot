# Bot de Proventos no Twitter (X)

Um bot automatizado no Twitter (X) que publica informações sobre proventos, incluindo datas e valores, com dados extraídos diretamente da CVM.

## Atencao
Esse repositorio esta configurado para rodar com GitHub Actions a cada hora, entao siga as instrucoes a seguir para nao quebrar nada:

1. De um 'git pull'
2. Comente as linhas de "Fluxo Principal" no arquivo main.py
3. No mesmo arquivo, descomente as linhas de teste com 20 arquivos e troque os links que quer testar em lista_de_links= []
4. Executando, voce tera a resposta de quais documentos de lista_de_links que tratam de proventos ou nao (True/False) e os respectivos dados para aqueles que sao True
5. Favor nao dar commit em nada na main para que os arquivos json locais e do repo nao fiquem diferentes pois pode causar uma confusao nos arquivos que o bot utiliza
6. Caso queira sugerir alguma alteracao, criar uma branch separada e fazer um PR

## To Do

1. Refatorar o algoritmo para melhorar legibilidade e facilitar atualizacoes futuras
2. Adicionar algumas funcionalidades(ex, buscar cnpj da empresa para procurar o ticker, maior filtragem para postar tweets, talvez a imagem como um comentario)
3. Melhorar funcao que captura imagem do doc pois esta falhando as vezes e sempre por esse motivo "Failed to open file 'temp.pdf"
4. Criar um .env.example
5. Usar Enum