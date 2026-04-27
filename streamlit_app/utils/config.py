EMAIL_ADMIN = "pablo.ti@caiuas.com.br"


















def tem_acesso(email_usuario, lista_emails):
    """Retorna True se o e-mail é admin ou está na lista do menu."""
    return email_usuario == EMAIL_ADMIN or email_usuario in lista_emails

# 2. Funções de Autenticação
