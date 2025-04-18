# Copyright 2021 Curtin University
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
#
# Author: Tuan Chien, Keegan Smith, Jamie Diprose

from __future__ import annotations

import os.path
from datetime import timedelta

import pendulum
import time_machine
from airflow.exceptions import AirflowException
from airflow.models import DagRun, DagModel
from airflow.models.dag import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.session import provide_session
from airflow.utils.state import State

from observatory_platform.airflow.sensors import DagCompleteSensor
from observatory_platform.sandbox.sandbox_environment import SandboxEnvironment
from observatory_platform.sandbox.test_utils import SandboxTestCase


def create_dag(
    *,
    start_date: pendulum.DateTime,
    ext_dag_ids: list[str],
    dag_id: str = "test_workflow",
    schedule: str = "@weekly",
    mode: str = "reschedule",
    check_exists: bool = True,
    catchup: bool = False,
):
    with DAG(dag_id=dag_id, schedule=schedule, start_date=start_date, catchup=catchup) as dag:

        def dummy_task():
            print("Hello world")

        sensors = []
        for ext_dag_id in ext_dag_ids:
            sensor = DagCompleteSensor(
                task_id=f"{ext_dag_id}_sensor",
                external_dag_id=ext_dag_id,
                mode=mode,
                poke_interval=int(1200),  # Check if dag run is ready every 20 minutes
                timeout=int(timedelta(days=1).total_seconds()),  # Sensor will fail after 1 day of waiting
                check_existence=check_exists,
            )
            sensors.append(sensor)

        # Use the PythonOperator to run the Python functions
        dummy_task_instance = PythonOperator(task_id="dummy_task", python_callable=dummy_task)

        # Define the task sequence
        sensors >> dummy_task_instance

    return dag


def make_dummy_dag(*, dag_id: str, schedule: str, start_date: pendulum.DateTime, fail: bool = False) -> DAG:
    """A Dummy DAG for testing purposes.

    :param dag_id: the DAG id.
    :param schedule: the schedule interval.
    :param start_date: the DAGs logical date.
    :param fail: Whether to intentionally fail the task
    :return: the DAG.
    """

    with DAG(
        dag_id=dag_id,
        schedule=schedule,
        default_args={"owner": "airflow", "start_date": start_date},
        catchup=False,
    ) as dag:

        def dummy_task():
            if fail:
                raise AirflowException("We have a problem!")
            return

        task1 = PythonOperator(task_id="dummy_task", python_callable=dummy_task)

    return dag


class TestDagCompleteSensor(SandboxTestCase):
    """Test the Task Window Sensor.  We use one of the stock example dags"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @provide_session
    def find_runs(self, session):
        return session.query(DagRun).all()

    @provide_session
    def update_db(self, *, session, object):
        session.merge(object)
        session.commit()

    def add_dummy_dag_model(self, *, tmp_dir: str, dag_id: str, schedule: str):
        model = DagModel()
        model.dag_id = dag_id
        model.schedule = schedule
        model.fileloc = os.path.join(tmp_dir, "dummy_dag.py")
        open(model.fileloc, mode="a").close()
        self.update_db(object=model)

    def test_sensor_success(self):
        env = SandboxEnvironment()
        with env.create():
            # Create Crossref Metadata DAG
            logical_date = pendulum.datetime(2024, 1, 7)
            crossref_dag = make_dummy_dag(dag_id="crossref_metadata", schedule="0 0 7 * *", start_date=logical_date)
            self.add_dummy_dag_model(
                tmp_dir=env.temp_dir, dag_id=crossref_dag.dag_id, schedule=crossref_dag.schedule_interval
            )

            # Run Crossref Metadata DAG run on Feb 7
            destination = pendulum.datetime(2024, 2, 7)
            with time_machine.travel(destination, tick=True):
                with env.create_dag_run(crossref_dag, logical_date):
                    ti = env.run_task("dummy_task")
                    self.assertEqual(State.SUCCESS, ti.state)

            # Run downstream dag: Sun 4th Feb - Sun 11th Feb
            logical_date = pendulum.datetime(2024, 2, 4)
            dag = create_dag(start_date=logical_date, ext_dag_ids=["crossref_metadata"], schedule="@weekly")
            destination = pendulum.datetime(2024, 2, 11)
            with time_machine.travel(destination, tick=True):
                with env.create_dag_run(dag=dag, logical_date=logical_date):
                    ti = env.run_task(f"crossref_metadata_sensor")
                    self.assertEqual(State.SUCCESS, ti.state)

                    ti = env.run_task(f"dummy_task")
                    self.assertEqual(State.SUCCESS, ti.state)

            # Run downstream dag: Sun 11th Feb - Sun 18th Feb
            # Should also work because there have been no more Crossref Metadat runs
            logical_date = pendulum.datetime(2024, 2, 11)
            dag = create_dag(start_date=logical_date, ext_dag_ids=["crossref_metadata"], schedule="@weekly")
            destination = pendulum.datetime(2024, 2, 18)
            with time_machine.travel(destination, tick=True):
                with env.create_dag_run(dag=dag, logical_date=logical_date):
                    ti = env.run_task(f"crossref_metadata_sensor")
                    self.assertEqual(State.SUCCESS, ti.state)

                    ti = env.run_task(f"dummy_task")
                    self.assertEqual(State.SUCCESS, ti.state)

    def test_sensor_up_for_reschedule(self):
        env = SandboxEnvironment()
        with env.create():
            # Create Crossref Metadata DAG
            logical_date = pendulum.datetime(2024, 1, 7)
            crossref_dag = make_dummy_dag(
                dag_id="crossref_metadata", schedule="0 0 7 * *", start_date=logical_date, fail=True
            )
            self.add_dummy_dag_model(
                tmp_dir=env.temp_dir, dag_id=crossref_dag.dag_id, schedule=crossref_dag.schedule_interval
            )

            # Run Crossref Metadata DAG run on Feb 7
            destination = pendulum.datetime(2024, 2, 7)
            with time_machine.travel(destination, tick=True):
                with env.create_dag_run(crossref_dag, logical_date):
                    with self.assertRaises(AirflowException):
                        env.run_task("dummy_task")
                    ti = env.get_task_instance("dummy_task")
                    self.assertEqual(State.FAILED, ti.state)

            # Run downstream dag: Sun 4th Feb - Sun 11th Feb
            logical_date = pendulum.datetime(2024, 2, 4)
            dag = create_dag(start_date=logical_date, ext_dag_ids=["crossref_metadata"], schedule="@weekly")
            destination = pendulum.datetime(2024, 2, 11)
            with time_machine.travel(destination, tick=True):
                with env.create_dag_run(dag=dag, logical_date=logical_date):
                    ti = env.run_task(f"crossref_metadata_sensor")
                    self.assertEqual(State.UP_FOR_RESCHEDULE, ti.state)

                    ti = env.run_task("dummy_task")
                    self.assertEqual(None, ti.state)

    def test_external_dag_run_after_data_interval(self):
        env = SandboxEnvironment()
        with env.create():
            # Create Unpaywall DAG
            logical_date = pendulum.datetime(2024, 1, 7, 0, 1)
            unpaywall_dag = make_dummy_dag(dag_id="unpaywall", schedule="1 0 * * *", start_date=logical_date, fail=True)
            self.add_dummy_dag_model(
                tmp_dir=env.temp_dir, dag_id=unpaywall_dag.dag_id, schedule=unpaywall_dag.schedule_interval
            )

            # Run Unpaywall DAG run on Feb 11
            logical_date = pendulum.datetime(2024, 2, 10, 0, 1)
            destination = pendulum.datetime(2024, 2, 11, 0, 1)
            with time_machine.travel(destination, tick=True):
                with env.create_dag_run(unpaywall_dag, logical_date):
                    with self.assertRaises(AirflowException):
                        env.run_task("dummy_task")
                    ti = env.get_task_instance("dummy_task")
                    self.assertEqual(State.FAILED, ti.state)

            # Run downstream dag: Sun 4th Feb - Sun 11th Feb
            # Set time to 1 hour past midnight
            logical_date = pendulum.datetime(2024, 2, 4)
            dag = create_dag(start_date=logical_date, ext_dag_ids=["unpaywall"], schedule="@weekly")
            destination = pendulum.datetime(2024, 2, 11, 1)
            with time_machine.travel(destination, tick=True):
                with env.create_dag_run(dag=dag, logical_date=logical_date):
                    ti = env.run_task(f"unpaywall_sensor")
                    self.assertEqual(State.SUCCESS, ti.state)

                    ti = env.run_task(f"dummy_task")
                    self.assertEqual(State.SUCCESS, ti.state)
