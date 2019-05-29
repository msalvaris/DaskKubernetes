"""Invoke module for kubectl
"""
import logging
import logging.config
from invoke import task, Collection
from dotenv import find_dotenv, set_key
from invoke.exceptions import Failure
from config import load_config
import os
from invoke.executor import Executor


@task
def get_nodes(c):
    c.run("kubectl get nodes", pty=True)

@task
def get_pods(c):
    c.run("kubectl get pods --all-namespaces", pty=True)

@task
def get_services(c):
    c.run("kubectl get services", pty=True)

@task
def install_nvidia(c):
    c.run("kubectl create -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/v1.11/nvidia-device-plugin.yml", pty=True)

@task
def install_blob(c):
    c.run("kubectl create -f https://raw.githubusercontent.com/Azure/kubernetes-volume-drivers/master/flexvolume/blobfuse/deployment/blobfuse-flexvol-installer-1.9.yaml", pty=True)


@task
def create_secrets(c, premium_account=None, premium_account_key=None):
    env_values = load_config()
    premium_account_key = env_values["ACCOUNT_KEY"] if premium_account_key is None else premium_account_key
    premium_account = env_values["ACCOUNT_NAME"] if premium_account is None else premium_account

    cmd = (
           f"kubectl create secret generic blobfusecreds "
           f"--from-literal accountname={premium_account} "
           f"--from-literal accountkey={premium_account_key} "
           f"--type='azure/blobfuse'"
    )
    c.run(cmd, pty=True)

    cmd = (
           f"kubectl create secret generic blobfusecredsmodel "
           f"--from-literal accountname={premium_account} "
           f"--from-literal accountkey={premium_account_key} "
           f"--type='azure/blobfuse'"
    )
    c.run(cmd, pty=True)


@task
def delete_secrets(c):
    c.run("kubectl delete secret blobfusecreds", pty=True)
    c.run("kubectl delete secret blobfusecredsmodel", pty=True)

@task
def install_helm(c):
    c.run("kubectl --namespace kube-system create sa tiller", pty=True)
    c.run("kubectl create clusterrolebinding tiller --clusterrole cluster-admin --serviceaccount=kube-system:tiller", pty=True)
    c.run("helm init --service-account tiller", pty=True)

@task
def scale(c, deployment, replicas):
    c.run(f"kubectl scale --replicas {replicas} deployment/{deployment}", pty=True)

@task
def describe_pods(c):
    c.run(f"kubectl describe pods", pty=True)

@task
def describe_node(c, node_name):
    c.run(f"kubectl describe node {node_name}", pty=True)

@task
def get_events(c):
    c.run(f"kubectl get events", pty=True)

