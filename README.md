# Batch scoring of Deep Learning models using Dask on Kubernetes
This repo contains a demonstration on how to score Deep Learning models on GPU using Dask and Kubernetes. The repo contains two scenarios:  
1.  Take a movie, split it into multiple images and run a simple [style transfer model](https://github.com/pytorch/examples/tree/master/fast_neural_style) on each of the images. Then stich the result back together to make a movie.  
2.  Take a movie, split it into multiple images and run [Mask-RCNN model](https://github.com/facebookresearch/maskrcnn-benchmark) over each image. Then stitch the resulting images together to make a movie.

It uses Azure Kubernetes Services but other cloud providers can be added (PRs welcome :))
## Prerequisites
Azure account
Linux VM/PC
Docker

> **Note:**
> You will need to run docker without sudo, to do this run:
> ```
> sudo usermod -aG docker $USER
> newgrp docker 
>```


## Setup
Once you have cloned the repo, you will need to create a .env file from [env_template](env_template)
Feel free to adjust any of the names for any of the resources. Don't worry about filling in the subscription id and account key these will be filled in by the scripts.
You need to specify the data (DATA variable) location which should be the absolute location on your VM or PC that you want mapped as a volume inside your control plane container.
You will also need to specify the container registry to use (CONTAINER_REGISTRY variable). This will be the registry used to host the images used on Kubernetes.

> **Note:**
> You will need to have logged in to your container registry account to be able to push the images to it
>

```bash
make setup
```

This will create the docker images used in the repo and push them to the specified container registry:
1. Control plane image which holds the environment we will use to orchestrate everything
2. Image that will be used for the Dask worker
3. Image used for Dask Scheduler
4. Image used for our Jupyter Lab service

Once the images are built and pushed run:
```bash
make run
```
To start the cotrol plane container and start running bash inside it.

From here you will have access to a set of commands orchestrated through [invoke](http://www.pyinvoke.org/). To see list of commands available simply run:
```bash
inv --list
```
Tab completion has also been added so you can also use that to see list of commands
Next run:
```bash
inv setup
```
This will:
- Log in using Azure CLI
- Create the blob storage and appropriate containers
- Create the Kubernetes cluster
- Install NVidia drivers
- Install Blob drivers
- Install Helm
- Add secrets for blob containers

You can deploy the style transfer scenario with:
```bash
inv helm.deploy --deployment-type style_transfer --replicas 1
```
or Mask-RCNN with:
```bash
inv helm.deploy --deployment-type mask_rcnn --replicas 1
```

Then once the containers are spun up (this can take 5-15 minutes) run:
```bash
inv kubectl.get-services
```
This will list the services available on your cluster:
The external-ip again the service ending in jupyter will be the jupyter lab interface and the service ending in scheduler will be the dask dashboard
Point your browser to the external ip of the jupyter lab service. Depending on what scenario you chose earlier you will have either a StyleTransferDemo notebook or MASKRCNNDaskDemo notebook.

To run the notebooks you will need some data to run against. To upload some demo videos to your blob storage run:
```bash
inv storage.copy-movies --destination-container data
```
This will copy some demo movies to the data container in your premium blob storage

If you wish to use your own movies run
```bash
inv storage.upload-from-local --destination movies --destination-container data --source movies
```
This will look for the directory movies in /data location inside the container and upload it to the data container as the directory movies
 
