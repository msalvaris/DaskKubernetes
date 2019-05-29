define PROJECT_HELP_MSG
Usage:
    make help                   show this message
    make build                  build docker image
    make push-dask				build and push images that will be used by Kubernetes and are reference in helm file
	setup 						runs both build and push-dask
endef
export PROJECT_HELP_MSG
PWD:=$(shell pwd)
PORT:=9999
NAME:=dask-playground # Name of running container

include .env

image_name:=$(CONTAINER_REGISTRY)/dask-playground
local_volumes:=-v $(PWD):/workspace \
			   -v $(DATA):/data
tag:=version_.009
docker_exec:=docker exec -it $(NAME)

help:
	echo "$$PROJECT_HELP_MSG" | less


### Build and Push Docker containers ###################################################################################

build: # Docker container for local control plane
	docker build -t $(image_name) -f Docker/dockerfile Docker


build-dask-worker-style-transfer:
	docker build -t $(CONTAINER_REGISTRY)/dask-style-transfer-worker:$(tag) --target style_transfer -f kubernetes_deployment/dask-docker/dockerfile .

build-dask-worker-maskrcnn:
	docker build -t $(CONTAINER_REGISTRY)/dask-maskrcnn-worker:$(tag) --target maskrcnn -f kubernetes_deployment/dask-docker/dockerfile .

build-dask-worker:build-dask-worker-style-transfer build-dask-worker-maskrcnn


build-dask-jupyter-style-transfer:
	docker build -t $(CONTAINER_REGISTRY)/dask-style-transfer-jupyter:$(tag) --target style_transfer -f kubernetes_deployment/dask-docker-jupyter/dockerfile .

build-dask-jupyter-maskrcnn:
	docker build -t $(CONTAINER_REGISTRY)/dask-maskrcnn-jupyter:$(tag) --target maskrcnn -f kubernetes_deployment/dask-docker-jupyter/dockerfile .

build-dask-jupyter: build-dask-jupyter-style-transfer build-dask-jupyter-maskrcnn


build-dask-scheduler-style-transfer:
	docker build -t $(CONTAINER_REGISTRY)/dask-style-transfer-scheduler:$(tag) --target style_transfer -f kubernetes_deployment/dask-docker-scheduler/dockerfile .

build-dask-scheduler-maskrcnn:
	docker build -t $(CONTAINER_REGISTRY)/dask-maskrcnn-scheduler:$(tag) --target maskrcnn -f kubernetes_deployment/dask-docker-scheduler/dockerfile .

build-dask-scheduler: build-dask-scheduler-style-transfer build-dask-scheduler-maskrcnn


build-dask: build-dask-worker build-dask-jupyter build-dask-scheduler
	@echo BUILT images

push-dask-worker: build-dask-worker
	docker push $(CONTAINER_REGISTRY)/dask-style-transfer-worker:$(tag)
	docker push $(CONTAINER_REGISTRY)/dask-maskrcnn-worker:$(tag)

push-dask-jupyter: build-dask-jupyter
	docker push $(CONTAINER_REGISTRY)/dask-style-transfer-jupyter:$(tag)
	docker push $(CONTAINER_REGISTRY)/dask-maskrcnn-jupyter:$(tag)

push-dask-scheduler: build-dask-scheduler
	docker push $(CONTAINER_REGISTRY)/dask-style-transfer-scheduler:$(tag)
	docker push $(CONTAINER_REGISTRY)/dask-maskrcnn-scheduler:$(tag)

push-dask: push-dask-worker push-dask-jupyter push-dask-scheduler
	@echo PUSHED images

setup: build push-dask
	@echo "All containers built"

### Control plane #######################################################################################################

run: # Run docker locally for dev and control
	docker run $(local_volumes) \
			   --name $(NAME) \
	           -d \
	           -v /var/run/docker.sock:/var/run/docker.sock \
			   -v ${HOME}/.bash_history:/root/.bash_history \
	           -e PYTHONPATH=/workspace:$$PYTHONPATH \
			   -e HIST_FILE=/root/.bash_history \
			   -e TAG=$(tag) \
	           -it $(image_name)

	$(docker_exec) bash

bash:
	$(docker_exec) bash


stop:
	docker stop $(NAME)
	docker rm $(NAME)


.PHONY: help build