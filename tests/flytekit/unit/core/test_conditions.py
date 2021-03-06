import typing

import pytest

from flytekit import task, workflow
from flytekit.common.translator import get_serializable
from flytekit.core.condition import conditional
from flytekit.core.context_manager import Image, ImageConfig, SerializationSettings


@task
def square(n: float) -> float:
    """
    Parameters:
        n (float): name of the parameter for the task will be derived from the name of the input variable
               the type will be automatically deduced to be Types.Integer

    Return:
        float: The label for the output will be automatically assigned and type will be deduced from the annotation

    """
    return n * n


@task
def double(n: float) -> float:
    """
    Parameters:
        n (float): name of the parameter for the task will be derived from the name of the input variable
               the type will be automatically deduced to be Types.Integer

    Return:
        float: The label for the output will be automatically assigned and type will be deduced from the annotation

    """
    return 2 * n


def test_condition_else_fail():
    @workflow
    def multiplier_2(my_input: float) -> float:
        return (
            conditional("fractions")
            .if_((my_input > 0.1) & (my_input < 1.0))
            .then(double(n=my_input))
            .elif_((my_input > 1.0) & (my_input < 10.0))
            .then(square(n=my_input))
            .else_()
            .fail("The input must be between 0 and 10")
        )

    with pytest.raises(ValueError):
        multiplier_2(my_input=10)


def test_condition_sub_workflows():
    @task
    def sum_div_sub(a: int, b: int) -> typing.NamedTuple("Outputs", sum=int, div=int, sub=int):
        return a + b, a / b, a - b

    @task
    def sum_sub(a: int, b: int) -> typing.NamedTuple("Outputs", sum=int, sub=int):
        return a + b, a - b

    @workflow
    def sub_wf(a: int, b: int) -> (int, int):
        return sum_sub(a=a, b=b)

    @workflow
    def math_ops(a: int, b: int) -> (int, int):
        # Flyte will only make `sum` and `sub` available as outputs because they are common between all branches
        sum, sub = (
            conditional("noDivByZero")
            .if_(a > b)
            .then(sub_wf(a=a, b=b))
            .else_()
            .fail("Only positive results are allowed")
        )

        return sum, sub

    x, y = math_ops(a=3, b=2)
    assert x == 5
    assert y == 1


def test_condition_tuple_branches():
    @task
    def sum_sub(a: int, b: int) -> typing.NamedTuple("Outputs", sum=int, sub=int):
        return a + b, a - b

    @workflow
    def math_ops(a: int, b: int) -> (int, int):
        # Flyte will only make `sum` and `sub` available as outputs because they are common between all branches
        sum, sub = (
            conditional("noDivByZero")
            .if_(a > b)
            .then(sum_sub(a=a, b=b))
            .else_()
            .fail("Only positive results are allowed")
        )

        return sum, sub

    x, y = math_ops(a=3, b=2)
    assert x == 5
    assert y == 1

    default_img = Image(name="default", fqn="test", tag="tag")
    serialization_settings = SerializationSettings(
        project="project",
        domain="domain",
        version="version",
        env=None,
        image_config=ImageConfig(default_image=default_img, images=[default_img]),
    )

    sdk_wf = get_serializable(serialization_settings, math_ops)
    assert sdk_wf.nodes[0].branch_node.if_else.case.then_node.task_node.reference_id.name == "test_conditions.sum_sub"


def test_condition_unary_bool():
    @task
    def return_true() -> bool:
        return True

    @workflow
    def failed() -> int:
        return 10

    @workflow
    def success() -> int:
        return 20

    with pytest.raises(AssertionError):

        @workflow
        def decompose_unary() -> int:
            result = return_true()
            return conditional("test").if_(result).then(success()).else_().then(failed())

    with pytest.raises(AssertionError):

        @workflow
        def decompose_none() -> int:
            return conditional("test").if_(None).then(success()).else_().then(failed())

    with pytest.raises(AssertionError):

        @workflow
        def decompose_is() -> int:
            result = return_true()
            return conditional("test").if_(result is True).then(success()).else_().then(failed())

    @workflow
    def decompose() -> int:
        result = return_true()
        return conditional("test").if_(result.is_true()).then(success()).else_().then(failed())

    assert decompose() == 20
