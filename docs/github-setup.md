# Configurar GitHub para `make demo-github`

Sustituye `OWNER` por tu usuario u organización. El repositorio debe ser público (o de un
plan que permita branch protection y auto-merge).

## 1. Crear los repositorios

```sh
cd ../news-api
gh repo create OWNER/news-api --public --source . --push
git push origin initial                      # etiqueta del estado inicial
cd ../technical-debt-automation
git init -b main && git add -A && git commit -m "Demo" # si aún no es un repositorio
gh repo create OWNER/technical-debt-automation --public --source . --push   # opcional
```

El primer push ejecuta `ci` en `main` y queda **rojo** a propósito: los tests pasan, la
auditoría falla. Espera a que termine; GitHub necesita haber visto el check `verify` una vez.

## 2. Secretos

GitHub Actions no necesita ningún secreto: CI no llama al modelo. Las credenciales viven
solo en tu terminal:

| Variable | Quién la usa | Permisos |
|---|---|---|
| `ANTHROPIC_API_KEY` (o `CLAUDE_CODE_OAUTH_TOKEN`) | contenedor del agente | una clave de demo con límite bajo |
| `GH_TOKEN` (opcional; si falta se usa la sesión de `gh auth login`) | `tda/publish.py` en el host | token de grano fino solo para `news-api`: *Contents* y *Pull requests* de lectura y escritura, **sin** *Workflows* |

Sin el permiso *Workflows*, GitHub rechaza cualquier push que modifique
`.github/workflows/`: una segunda barrera para el archivo de CI.

## 3. Auto-merge y protección de `main`

```sh
gh api -X PATCH repos/OWNER/news-api -F allow_auto_merge=true -F delete_branch_on_merge=true
gh api -X PUT repos/OWNER/news-api/branches/main/protection --input - <<'JSON'
{
  "required_status_checks": {"strict": false, "checks": [{"context": "verify"}]},
  "enforce_admins": true,
  "required_pull_request_reviews": null,
  "restrictions": null
}
JSON
```

Esto marca `verify` como check requerido y aplica la regla también a administradores.
Para exigir además una aprobación humana, define `required_pull_request_reviews`.
`publish.py` solo pide auto-merge si ve `verify` entre los checks requeridos.

## 4. Ejecutar

```sh
make demo-github TDA_REPO=OWNER/news-api
gh pr checks --repo OWNER/news-api --watch <número>   # verify → merge automático
```

## 5. Volver al estado inicial

```sh
gh api -X DELETE repos/OWNER/news-api/branches/main/protection
git -C ../news-api push --force origin initial:main
# vuelve a aplicar el paso 3
```

Las ramas `debt/*` ya integradas se borran solas; cierra los PR que hayan quedado abiertos.
