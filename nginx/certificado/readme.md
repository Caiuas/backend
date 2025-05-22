# Pasta para salvar os arquivos
cert.pem
key.pem
Gerados com comando:

sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout nginx/certificado/key.pem -out nginx/certificado/cert.pem