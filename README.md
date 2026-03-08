# Qwen OAuth Proxy — Home Assistant Addon

OpenAI-compatible прокси для Qwen через OAuth токен (portal.qwen.ai).  
Использует [aptdnfapt/qwen-code-oai-proxy](https://github.com/aptdnfapt/qwen-code-oai-proxy) как движок.

## Установка

1. **Настройки → Дополнения → Магазин → ⋮ → Пользовательские репозитории**
2. Добавить URL этого репозитория, тип — **Add-on**
3. Установить **Qwen OAuth Proxy**

## Конфигурация

Значения из `~/.qwen/oauth_creds.json`:

```yaml
access_token: ""
refresh_token: ""
expiry_date: 
```

## Extended OpenAI Conversation

| Поле | Значение |
|---|---|
| API Key | `qwen` |
| Base URL | `http://homeassistant.local:8080/v1` |
| Model | `qwen3-coder-plus` |

## Доступные модели

- `qwen3-coder-plus` — основная (рекомендуется)
- `qwen3-coder-flash` — быстрая
- `qwen3.5-plus` — новейшая
