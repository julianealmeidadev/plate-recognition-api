# 🚗 Projeto de Reconhecimento de Placas
Projeto experimental para envio e processamento de imagens com o objetivo de identificar placas veiculares.

A aplicação utiliza **Node.js com Express** para receber imagens por upload e executa um script em **Python** responsável pelo processamento da imagem.

## 🎯 Objetivo
O projeto foi criado para estudar a integração entre aplicações Node.js e Python, upload de arquivos e processamento de imagens.

O fluxo atual funciona da seguinte forma:

1. O usuário envia uma imagem para a API.
2. O servidor Node.js recebe o arquivo utilizando Multer.
3. A imagem é armazenada temporariamente.
4. O servidor executa o script Python.
5. O script realiza o processamento da imagem.
6. O resultado é devolvido pela API.
7. O arquivo temporário é removido do servidor.

## 🛠️ Tecnologias utilizadas

### Backend
- Node.js
- Express.js
- Multer

### Processamento de imagem
- Python
- OpenCV

## 📁 Estrutura do projeto
```text
Projeto-placa/
├── plate_recognition.py
├── server.js
├── package.json
├── package-lock.json
└── .gitignore
```
## 🚀 Como executar
### Pré-requisitos

Antes de iniciar, tenha instalado:

Node.js
npm
Python
OpenCV para Python

1. Clone o repositório
`git clone https://github.com/julianealmeidadev/Projeto-placa.git
cd Projeto-placa`
2. Instale as dependências do Node.js
`npm install`
3. Instale o OpenCV no Python
`pip install opencv-python`
4. Inicie o servidor
`node server.js`

O servidor ficará disponível em:
http://localhost:8000

### 📡 Rotas disponíveis
Teste da API
POST /test

Retorno:

Rota POST de teste funcionando!
Upload de imagem
POST /upload

O campo enviado deve se chamar:

  image

Exemplo de resposta:

Placa reconhecida: ABC1234
⚠️ Estado atual do projeto

O fluxo de upload e comunicação entre Node.js e Python já está implementado.

O reconhecimento real da placa ainda está em desenvolvimento. Atualmente, o script Python utiliza um retorno de teste para validar a integração entre as tecnologias.

## 🔜 Próximas melhorias
Implementar reconhecimento real de caracteres da placa
Aplicar processamento de imagem com OpenCV
Detectar automaticamente a região da placa
Integrar OCR
Validar placas nos padrões Mercosul e antigo
Melhorar tratamento de erros
Criar interface web para envio de imagens
Adicionar testes automatizados
Criar documentação da API

## 💡 Aprendizados
Este projeto envolve conceitos como:

criação de APIs com Express
upload de arquivos com Multer
integração entre Node.js e Python
execução de scripts externos
manipulação de arquivos temporários
processamento de imagens com OpenCV

## 👩‍💻 Autora
Juliane Almeida
Github: https://github.com/julianealmeidadev
