buildx:
	docker buildx build --platform linux/amd64,linux/arm64 -t ghcr.io/beanpuppy/discord-cat:latest . --push

buildx-load:
	docker buildx build --platform linux/amd64,linux/arm64 -t ghcr.io/beanpuppy/discord-cat:latest . --load
