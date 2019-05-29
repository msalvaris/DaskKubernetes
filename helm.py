"""Invoke module for Helm
"""
import logging
import logging.config
from invoke import task, Collection
from dotenv import find_dotenv, set_key
from invoke.exceptions import Failure
from config import load_config
import os
from invoke.executor import Executor


tag = os.getenv("TAG")


@task
def upgrade(c):
    c.run(f"helm init --upgrade", pty=True)

@task
def version(c):
    c.run(f"helm version", pty=True)

@task
def update(c):
    c.run(f"helm repo update", pty=True)


def _style_transfer_cmd(replicas, dry_run=False):
    dry_run_switch = "--dry-run" if dry_run else ""
    return (
           f"helm install {dry_run_switch} --debug "
           f"-f ./kubernetes_deployment/helm-chart/values_gpu.yaml "
           f"--set scheduler.image.tag='{tag}' "
           f"--set worker.image.tag='{tag}' "
           f"--set jupyter.image.tag='{tag}' "
           f"--set worker.replicas={replicas} "
           f"./kubernetes_deployment/helm-chart/dask "
    )

def _mask_rcnn_cmd(replicas, dry_run=False):
    dry_run_switch = "--dry-run" if dry_run else ""
    return (
           f"helm install {dry_run_switch} --debug "
           f"-f ./kubernetes_deployment/helm-chart/values_gpu.yaml "
           f"--set scheduler.image.repository='masalvar/dask-maskrcnn-scheduler' "
           f"--set worker.image.repository='masalvar/dask-maskrcnn-worker' "
           f"--set jupyter.image.repository='masalvar/dask-maskrcnn-jupyter' "
           f"--set scheduler.image.tag='{tag}' "
           f"--set worker.image.tag='{tag}' "
           f"--set jupyter.image.tag='{tag}' "
           f"--set worker.replicas={replicas} "
           f"./kubernetes_deployment/helm-chart/dask"
    )

_DEPLOYMENT_COMMANDS={
    "style_transfer": _style_transfer_cmd,
    "mask_rcnn": _mask_rcnn_cmd
}

@task
def deploy(c, deployment_type, replicas, dry_run=False):
    logger = logging.getLogger(__name__)
    try:
        cmd = _DEPLOYMENT_COMMANDS[deployment_type](replicas, dry_run=dry_run)
        c.run(cmd)
    except KeyError:
        logger.warning(f"Deployment {deployment_type} not found. Deployments available are {str(list(_DEPLOYMENT_COMMANDS.keys()))}")


@task(name='list')
def hlist(c):
    c.run("helm list --all")


@task
def delete(c, deployment): 
    c.run(f"helm delete {deployment}")


@task
def status(c, deployment):
    c.run(f"helm status {deployment}")