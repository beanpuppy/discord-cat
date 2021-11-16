buildx:
	docker buildx build --platform linux/amd64,linux/arm64 -t ghcr.io/beanpuppy/discord-mc-status:latest . --push

buildx-load:
	docker buildx build --platform linux/amd64,linux/arm64 -t ghcr.io/beanpuppy/discord-mc-status:latest . --load
