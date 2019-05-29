import logging
import logging.config
from invoke import task, Collection
from dotenv import find_dotenv, set_key
from invoke.exceptions import Failure
from config import load_config
import os
from invoke.executor import Executor
import storage
import helm
import kubectl
import json


logging.config.fileConfig(os.getenv("LOG_CONFIG", "logging.conf"))
env_values = load_config()


def _is_loged_in(c):
    try:
        result = c.run("az account show", hide="both")
        return "Please run 'az login'" not in result.stdout
    except Failure:
        return False


def _prompt_sub_id_selection(c):
    # Importing here to avoid overhead to the rest of the application
    from tabulate import tabulate
    from toolz import pipe
    import json
    from prompt_toolkit import prompt

    results = c.run(f"az account list", pty=True, hide="out")
    sub_dict = json.loads(results.stdout)
    sub_list = [
        {"Index": i, "Name": sub["name"], "id": sub["id"]}
        for i, sub in enumerate(sub_dict)
    ]
    pipe(sub_list, tabulate, print)
    prompt_result = prompt("Please type in index of subscription you want to use: ")
    sub_id = sub_list[int(prompt_result)]["id"]
    print(f"You selected index {prompt_result} sub id {sub_id}")
    return sub_id


@task
def select_subscription(c, sub_id=env_values.get("SUBSCRIPTION_ID", None)):
    """Select Azure subscription to use
    
    Note:
        If sub_id isn't provided or found in env values interactive prompt is created asking for sub id selection
        The selection is then recorded in the env file

    Args:
        sub_id (string, optional): [description]. Defaults to env_values.get("SUBSCRIPTION_ID", None).
    """
    env_file = find_dotenv(raise_error_if_not_found=True)
    if sub_id is None or sub_id == "":
        sub_id = _prompt_sub_id_selection(c)
        set_key(env_file, "SUBSCRIPTION_ID", sub_id)
    c.run(f"az account set -s {sub_id}", pty=True)


@task(post=[select_subscription])
def login(c):
    """Log in to Azure CLI
    """
    if _is_loged_in(c):
        return None
    c.run("az login -o table", pty=True)


def _registered_container_services(c):
    cmd_results = c.run(f"az provider show -n Microsoft.ContainerService", pty=True)
    cmd_dict = json.loads(cmd_results.stdout)
    return cmd_dict["registrationState"] == "Registered"


@task
def register_container_services(c):
    """Register to use Container Services
    """
    logger = logging.getLogger(__name__)
    if not _registered_container_services(c):
        logger.info("Registering for Container Services")
        c.run(
            f"az provider register -n Microsoft.ContainerService",
            pty=True,
        )


@task
def aks_versions(c, location=env_values["REGION"]):
    c.run(f"az aks get-versions -l {location} -o table", pty=True)


@task
def get_kubectl_credentials(
    c, resource_group=env_values["RESOURCE_GROUP"], aks_name=env_values["AKS_NAME"]
):
    """Gets and stores the credentials for the Kubernetes cluster for kubectl to use

    Args:
        resource_group (string, optional): Resource group name. Defaults to env_values["RESOURCE_GROUP"].
        aks_name (string, optional): AKS name. Defaults to env_values["AKS_NAME"].

    """
    c.run(
        f"az aks get-credentials --resource-group {resource_group} --name {aks_name}",
        pty=True,
    )


@task(pre=[register_container_services], post=[get_kubectl_credentials])
def aks_create(
    c,
    resource_group=env_values["RESOURCE_GROUP"],
    aks_name=env_values["AKS_NAME"],
    node_count=3,
    vm_type="Standard_NC24rs_v3",
):
    """Creates AKS cluster
    
    Args:
        resource_group (str, optional): Resource group to associate the Kubernetes cluster with. Defaults to env_values["RESOURCE_GROUP"].
        aks_name (str, optional): The name of your Kubernetes cluster on Azure. Defaults to env_values["AKS_NAME"].
        node_count (int, optional): Number of nodes to create. Defaults to 3.
        vm_type (str, optional): VM type to use in cluster. Defaults to "Standard_NC24rs_v3".
    """
    cmd = (
        f"az aks create --resource-group {resource_group} "
        f"--name {aks_name} "
        f"--node-count {node_count} "
        f"--generate-ssh-keys "
        f"-s  {vm_type} "
        f"--kubernetes-version 1.11.8 "
    )  
    c.run(cmd, pty=True)


@task
def install_kubectl(c):
    c.run("az aks install-cli", pty=True)


@task
def remove_kubectl_credentials(c):
    c.run("rm /root/.kube/config", pty=True)


@task
def delete_resource_group(
    c, resource_group=env_values.get("RESOURCE_GROUP"), wait=False
):
    cmd = f"az group delete -n {resource_group} -y "
    if not wait:
        cmd = cmd + " --no-wait"
    c.run(cmd)


@task
def create_containers(c):
    logger = logging.getLogger(__name__)
    container_list = ("data", "models", "output")
    for container in container_list:
        logger.info(f"Creating container {container}")
        c.invoke_execute(c, "storage.create_container", container_name=container)


@task(
    pre=[
        login,
        create_containers,
        aks_create,
        kubectl.install_nvidia,
        kubectl.install_blob,
        kubectl.install_helm,
        kubectl.create_secrets
    ]
)
def setup(c):
    """Setup cluster and install NVidia and Azure Blob drivers

    It will carry out the following:
    - Log in using Azure CLI
    - Create the blob storage and appropriate containers
    - Create the Kubernetes cluster
    - Install NVidia drivers
    - Install Blob drivers
    - Install Helm
    - Add secrets for blob containers
    
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Setup complete")


def invoke_execute(context, command_name, **kwargs):
    """
    Helper function to make invoke-tasks execution easier.
    """
    results = Executor(namespace, config=context.config).execute((command_name, kwargs))
    target_task = context.root_namespace[command_name]
    return results[target_task]


namespace = Collection(
    login,
    setup,
    get_kubectl_credentials,
    remove_kubectl_credentials,
    install_kubectl,
    aks_create,
    aks_versions,
    register_container_services,
    delete_resource_group,
)

storage_collection = Collection.from_module(storage)
namespace.add_collection(storage_collection)

kubectl_collection = Collection.from_module(kubectl)
namespace.add_collection(kubectl_collection)

helm_collection = Collection.from_module(helm)
namespace.add_collection(helm_collection)

namespace.configure({"root_namespace": namespace, "invoke_execute": invoke_execute})

