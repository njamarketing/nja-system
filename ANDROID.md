# Iniciar o NJA no Android

Inicializador preparado para executar no Pydroid 3 (Python 3.10 ou superior).
Validado com testes locais em Python; não foi testado em um aparelho Android.

1. Baixe e extraia **NJA-System-v1.zip** inteiro em uma pasta acessível ao Pydroid. Não execute de dentro do ZIP.
2. No menu **Pip** do Pydroid, instale `tzdata`. Para fotos e integrações criptografadas, instale também `Pillow` e `cryptography`. A disponibilidade desses dois pacotes depende da instalação Android; se a instalação falhar, envie a mensagem do Pip para diagnóstico. Não é necessário instalar Gunicorn.
3. Abra `nja-system/iniciar_android.py` no editor do Pydroid e toque em **Executar ▶**.
4. Na primeira execução, informe nome, e-mail e senha de pelo menos 10 caracteres para criar o administrador. Em terminais sem entrada oculta, o Python poderá avisar que a senha será visível enquanto você digita.
5. O navegador será acionado. Se não abrir, acesse **http://localhost:8000** no próprio celular e entre com a conta criada.

Nas próximas vezes, basta executar o mesmo arquivo. Contas existentes são preservadas. Para encerrar, use Parar no Pydroid ou Ctrl+C no terminal.

## Dados e disponibilidade

O banco, os anexos e as chaves ficam em `nja-system/data`. Guarde essa pasta; não apague ao atualizar o código. Para copiar os dados, primeiro encerre o sistema e copie a pasta completa para um local seguro. Ela contém informações privadas.

Esta execução é local, acessível somente no próprio celular. Não sincroniza automaticamente com a VPS da Locaweb. Integrações externas continuam exigindo suas credenciais e configuração; webhooks públicos e callbacks de produção precisam do servidor publicado.

Mantenha o Pydroid em execução. Se o Android suspender ou fechar o aplicativo, o acesso e o processamento dos lembretes param. Se isso acontecer ao alternar para o navegador, confira as restrições de bateria do aplicativo. Este inicializador não cria um serviço permanente do Android.

## Se não iniciar

- **Arquivo app.py não encontrado:** extraia o pacote completo e mantenha os arquivos juntos.
- **Sem tzdata:** instale `tzdata` pelo Pip e execute novamente.
- **Sem scrypt:** o interpretador precisa oferecer `hashlib.scrypt`; o inicializador não reduz a proteção das senhas para contornar essa ausência.
- **Porta ocupada:** encerre a execução anterior antes de iniciar outra.
- **Sem permissão para gravar:** mova a pasta extraída para um local acessível ao Pydroid.
- **Foto ou integração indisponível:** confirme a instalação de `Pillow` e `cryptography` e a configuração da integração correspondente.
