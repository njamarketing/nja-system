# Pipeline de produção — GitHub Actions

A pipeline executa os testes em pushes e pull requests. O deploy acontece somente ao publicar uma tag iniciada por `v` ou ao executar manualmente o workflow **NJA System pipeline**. A imagem é construída no GitHub e enviada pronta por SSH; a VPS não precisa acessar um registry Docker.

## 1. Confirmar a arquitetura da VPS

No servidor:

```bash
uname -m
```

O padrão da pipeline é `linux/amd64`, correspondente a `x86_64`. Se o resultado for `aarch64`, crie no GitHub a variável de repositório `PROD_PLATFORM=linux/arm64` antes do primeiro deploy.

## 2. Criar a chave exclusiva de deploy

Em uma máquina administrativa, fora da pasta do projeto:

```bash
ssh-keygen -t ed25519 -C github-actions-nja -f nja-deploy-key
```

Guarde `nja-deploy-key` como segredo do GitHub. O arquivo `nja-deploy-key.pub` será instalado na VPS.

## 3. Preparar o usuário da VPS

Como `root`, crie um usuário sem senha e os diretórios necessários:

```bash
id nja-deploy >/dev/null 2>&1 || adduser --disabled-password --gecos "" nja-deploy
install -d -m 700 -o nja-deploy -g nja-deploy /home/nja-deploy/.ssh
install -d -m 700 -o nja-deploy -g nja-deploy /home/nja-deploy/incoming
install -d -m 700 -o 10001 -g 10001 /www/backup/nja
touch /home/nja-deploy/.ssh/authorized_keys
chown nja-deploy:nja-deploy /home/nja-deploy/.ssh/authorized_keys
chmod 600 /home/nja-deploy/.ssh/authorized_keys
```

Acrescente o conteúdo de `nja-deploy-key.pub` em `/home/nja-deploy/.ssh/authorized_keys`. É recomendável prefixar a linha com:

```text
no-agent-forwarding,no-port-forwarding,no-X11-forwarding,no-pty
```

## 4. Instalar os arquivos protegidos de deploy

Envie `deploy/nja-deploy` e `deploy/compose.production.yaml` para a VPS. Na pasta que recebeu os arquivos, execute como `root`:

```bash
install -d -m 755 /etc/nja-system
install -m 755 deploy/nja-deploy /usr/local/sbin/nja-deploy
install -m 644 deploy/compose.production.yaml /etc/nja-system/compose.production.yaml
printf '%s\n' 'nja-deploy ALL=(root) NOPASSWD: /usr/local/sbin/nja-deploy' > /etc/sudoers.d/nja-deploy
chmod 440 /etc/sudoers.d/nja-deploy
visudo -cf /etc/sudoers.d/nja-deploy
```

O script e o Compose ficam fora da pasta atualizável do projeto para que apenas o administrador possa alterá-los.

Antes do primeiro deploy, confirme que o contêiner atual consegue gravar no diretório de backup:

```bash
container_web=$(docker ps --filter 'label=com.docker.compose.project=nja-system' --filter 'label=com.docker.compose.service=web' --format '{{.ID}}' | head -n 1)
test -n "$container_web" && docker exec "$container_web" sh -c 'test -w /var/backups/nja'
```

O comando deve terminar sem mensagem e com código zero. Se falhar, não execute o workflow ainda: confira se o `compose.override.yaml` atual monta `/www/backup/nja:/var/backups/nja` no serviço `web` e recrie o contêiner com essa configuração.

## 5. Cadastrar os segredos no GitHub

Em **Settings → Secrets and variables → Actions**, cadastre:

- `PROD_HOST`: IP ou domínio SSH da VPS.
- `PROD_PORT`: porta SSH, normalmente `22`.
- `PROD_SSH_KEY`: conteúdo completo de `nja-deploy-key`.
- `PROD_KNOWN_HOSTS`: linha confiável da chave de host da VPS.

Obtenha a linha de `PROD_KNOWN_HOSTS` em uma máquina confiável:

```bash
ssh-keyscan -p 22 -t ed25519 191.252.60.226
```

Antes de salvar, compare a impressão digital com a exibida diretamente na VPS:

```bash
ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

Crie também o ambiente `production` em **Settings → Environments**. Se o seu plano permitir, habilite aprovação obrigatória e restrinja o ambiente a tags `v*`.

## 6. Primeiro deploy

Confirme antes que a versão atual está funcionando e que `/www/wwwroot/nja-system/.env` e `/www/backup/nja` permanecem no servidor. Depois, use **Actions → NJA System pipeline → Run workflow**.

Para os próximos releases, crie uma tag:

```bash
git tag v1.18.0
git push origin v1.18.0
```

Cada execução cria um backup, mantém o volume Docker `nja-system_nja-data`, publica a imagem nova e realiza rollback automático se `http://127.0.0.1:8000/` não responder em até 60 segundos. Nunca use `docker compose down -v`.

Depois que a pipeline assumir a produção, use o Compose protegido para inspecionar o serviço:

```bash
NJA_IMAGE=$(sed -n 's/^NJA_IMAGE=//p' /var/lib/nja-deploy/current.env) \
  docker compose -p nja-system -f /etc/nja-system/compose.production.yaml ps
```

Evite executar `docker compose up` a partir de `/www/wwwroot/nja-system`, pois aquele Compose ainda contém `build: .` e pode substituir a imagem publicada pela pipeline.
