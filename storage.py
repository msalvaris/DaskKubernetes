from invoke import task
from dotenv import set_key, find_dotenv
import json
from config import load_config
import logging
import os
from collections import namedtuple

env_values = load_config()


def _storage_exists(c, account_name):
    cmd = f"az storage account check-name -n {account_name}"
    result = c.run(cmd)
    json_payload = json.loads(result.stdout)
    return not json_payload["nameAvailable"]


@task
def create_resource_group(
    c, region=env_values.get("REGION"), resource_group=env_values.get("RESOURCE_GROUP")
):
    logger = logging.getLogger(__name__)
    logger.info(f"Creating resource group {resource_group}")
    cmd = f"az group create --location {region} " f"--name {resource_group} "
    c.run(cmd)


@task(pre=[create_resource_group])
def create_premium_storage(
    c,
    region=env_values.get("REGION"),
    account_name=env_values.get("ACCOUNT_NAME"),
    resource_group=env_values.get("RESOURCE_GROUP"),
):
    """Creates premium storage account. By default the values are loaded from the local .env file
    
    Args:
        region (string, optional): The region in which to create the storage account. Defaults to env_values.get("REGION").
        account_name (string, optional): The storage account name to use. Defaults to env_values.get("ACCOUNT_NAME").
        resource_group (string, optional): The resource group to associate the storage account with. Defaults to env_values.get("RESOURCE_GROUP").
    """
    logger = logging.getLogger(__name__)
    if _storage_exists(c, account_name):
        logger.info(f"Storage {account_name} exists")
        return None

    logger.info("Creating premium storage account")
    cmd = (
        f"az storage account create --location {region} "
        f"--name {account_name} "
        f"--resource-group {resource_group} "
        f"--kind BlockBlobStorage "
        f"--sku Premium_LRS "
    )
    c.run(cmd)


@task(pre=[create_premium_storage])
def store_key(c):
    """Retrieves premium storage account key from Azure and stores it in .env file
    """
    logger = logging.getLogger(__name__)
    account_name = env_values.get("ACCOUNT_NAME")
    resource_group = env_values.get("RESOURCE_GROUP")

    if (
        "ACCOUNT_KEY" in env_values
        and env_values["ACCOUNT_KEY"]
        and len(env_values["ACCOUNT_KEY"]) > 0
    ):
        logger.info(f"Account key already in env file")
        return None

    cmd = f"az storage account keys list -n {account_name} -g {resource_group}"
    result = c.run(cmd)
    keys = json.loads(result.stdout)
    env_file = find_dotenv(raise_error_if_not_found=True)
    set_key(env_file, "ACCOUNT_KEY", keys[0]["value"])


def _container_exists(c, container_name, account_name, account_key):
    cmd = (
        f"az storage container exists"
        f" --account-name {account_name}"
        f" --account-key {account_key}"
        f" --name {container_name}"
    )
    result = c.run(cmd)
    json_payload = json.loads(result.stdout)
    return json_payload["exists"]


@task(pre=[store_key])
def create_container(c, container_name):
    """Creates container based on the parameters found in the .env file
    """
    logger = logging.getLogger(__name__)
    env_values = load_config()
    account_name = env_values.get("ACCOUNT_NAME")
    account_key = env_values.get("ACCOUNT_KEY")
    if _container_exists(c, container_name, account_name, account_key):
        logger.info(f"Container {container_name} already exists")
        return None

    cmd = (
        f"az storage container create"
        f" --account-name {account_name}"
        f" --account-key {account_key}"
        f" --name {container_name}"
    )
    c.run(cmd)


def upload_data_from_to(
    c, remote_path, local_path, container_name, account_name, account_key
):
    cmd = (
        f"azcopy --source {local_path} --destination  https://{account_name}.blob.core.windows.net/{container_name}/{remote_path} "
        f"--dest-key {account_key} --quiet --recursive --exclude-older"
    )
    c.run(cmd, pty=True)


@task
def upload_from_local(c, source, destination, destination_container):
    """Upload local file or foler to container in premium blob 
    
    Args:
        source (str): File or folder found in /data that you want transfered to blob storage
        destination (str): Corresponding filename or foldername to have it transfered to in blob storage
        destination_container (str): Container to upload the source to
    """
    c.invoke_execute(
        c, "storage.create_container", container_name=destination_container
    )
    env_values = load_config()
    account_name = env_values.get("ACCOUNT_NAME")
    account_key = env_values.get("ACCOUNT_KEY")
    upload_data_from_to(
        c,
        destination,
        os.path.join("/data", source),
        destination_container,
        account_name,
        account_key,
    )


Movie = namedtuple("Movie", ["sas", "filename"])


def _transfer_using_sas(
    c, movie_sas, account_name, account_key, destination_container, destination
):
    cmd = (
        f'azcopy --source "{movie_sas}" --destination https://{account_name}.blob.core.windows.net/{destination_container}/{destination} '
        f"--dest-key {account_key} --quiet --exclude-older"
    )
    print(cmd)
    c.run(cmd, pty=True)


_MOVIES = (
    Movie(
        sas="https://happypathspremium.blob.core.windows.net/movies/climbing.mp4?st=2019-05-27T13%3A14%3A10Z&se=2030-05-28T13%3A14%3A00Z&sp=rl&sv=2018-03-28&sr=b&sig=zwrdFPZo%2F8z9eb12HndzvA020X3MOGDgUmHIlDJwp8Y%3D",
        filename="climbing.mp4",
    ),
    Movie(
        sas="https://happypathspremium.blob.core.windows.net/movies/people_10.mp4?st=2019-05-30T07%3A57%3A02Z&se=2030-05-31T07%3A57%3A00Z&sp=rl&sv=2018-03-28&sr=b&sig=gbyC50EbB8SJjUgO0Bc8YWfm5eAIIh4vqBq%2FCNZu4ms%3D",
        filename="people_10.mp4",
    ),
)


@task
def copy_movies(c, destination_container):
    """Copies demo movies to own storage
    
    Args:
        destination_container (str): Name of the container to copy the movies to
    """
    c.invoke_execute(
        c, "storage.create_container", container_name=destination_container
    )
    env_values = load_config()
    account_name = env_values.get("ACCOUNT_NAME")
    account_key = env_values.get("ACCOUNT_KEY")
    for movie in _MOVIES:
        _transfer_using_sas(
            c,
            movie.sas,
            account_name,
            account_key,
            destination_container,
            movie.filename,
        )

