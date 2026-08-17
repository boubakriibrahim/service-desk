# Optional model setup

The default demo uses fixed sample answers. You can run it without model accounts, API keys, or downloaded model weights.

Use this guide only when you want a real model to check requests, create search vectors, or write reports. Keep private keys in `.env`. The project ignores that file.

## Run the local request checker in Docker

Set these values in `.env`:

```env
LOCAL_RUNN=docker
LAYA_MODE=remote
LAYA_REQUIRED=false
```

Then start the app with `make up`. This enables the optional request-check service in Docker. Its first request may take longer while the model loads.

## Run local models on your computer

On a Mac or Linux computer with `uv` installed, set:

```env
LOCAL_RUNN=native
LAYA_MODE=remote
```

Then run `make up`. The setup creates a local Python environment and starts the request-check and embedding services. The first setup downloads their model files. This environment is ignored by Git.

## Connect a writing model

Set the model service address and model name in `.env`:

```env
AI_MODE=openai_compatible
AI_BASE_URL=https://your-model-service.example/v1
AI_API_KEY=your-private-key
AI_MODEL=your-model-name
AI_PROVIDER_KIND=cloud
AI_MAX_SENSITIVITY=internal
```

Use the address and model name supplied by your model provider. Do not commit the real API key.

## Connect an embedding service

Document search uses the demo mode by default. To use an OpenAI-compatible embedding service, set:

```env
EMBEDDING_MODE=openai_compatible
EMBEDDING_BASE_URL=https://your-embedding-service.example/v1
EMBEDDING_API_KEY=your-private-key
EMBEDDING_MODEL=your-embedding-model
```

Keep real keys only in `.env`. The example values above are placeholders.
