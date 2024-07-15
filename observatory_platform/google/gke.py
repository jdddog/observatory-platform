# Copyright 2023 Curtin University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

from airflow.providers.cncf.kubernetes.hooks.kubernetes import KubernetesHook
import kubernetes
from kubernetes import client


def gke_create_volume(*, kubernetes_conn_id: str, volume_name: str, size_gi: int):
    """

    :param kubernetes_conn_id:
    :param volume_name:
    :param size_gi:
    :return: None.
    """

    # Make Kubernetes API Client from Airflow Connection
    hook = KubernetesHook(conn_id=kubernetes_conn_id)
    api_client = hook.get_conn()
    v1 = kubernetes.client.CoreV1Api(api_client=api_client)

    # Create the PersistentVolume
    capacity = {"storage": f"{size_gi}Gi"}

    # Create PersistentVolumeClaim
    namespace = hook.get_namespace()
    namespace = "coki-astro"
    # TODO: Fix this. the get_namespace() returns None
    pvc = client.V1PersistentVolumeClaim(
        api_version="v1",
        kind="PersistentVolumeClaim",
        metadata=client.V1ObjectMeta(name=volume_name),
        spec=client.V1PersistentVolumeClaimSpec(
            access_modes=["ReadWriteOnce"],
            resources=client.V1ResourceRequirements(requests=capacity),
            storage_class_name="standard",
        ),
    )
    v1.create_namespaced_persistent_volume_claim(namespace=namespace, body=pvc)
    try:
        v1.create_namespaced_persistent_volume_claim(namespace=namespace, body=pvc)
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 409:
            logging.warn(f"PVC {volume_name} already exists.")
        else:
            raise e


def gke_delete_volume(*, kubernetes_conn_id: str, volume_name: str):
    """

    :param kubernetes_conn_id:
    :param namespace:
    :param volume_name:
    :return: None.
    """

    # Make Kubernetes API Client from Airflow Connection
    hook = KubernetesHook(conn_id=kubernetes_conn_id)
    api_client = hook.get_conn()
    v1 = kubernetes.client.CoreV1Api(api_client=api_client)

    # Delete VolumeClaim and Volume
    namespace = hook.get_namespace()
    namespace = "coki-astro"
    # TODO: Fix this. the get_namespace() returns None
    try:
        v1.delete_namespaced_persistent_volume_claim(name=volume_name, namespace=namespace)
    except kubernetes.client.exceptions.ApiException as e:
        if e.status == 404:
            logging.info(
                f"gke_delete_volume: PersistentVolumeClaim with name={volume_name}, namespace={namespace} does not exist"
            )
        else:
            raise e
