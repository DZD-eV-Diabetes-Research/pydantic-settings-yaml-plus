from typing import List, Dict, Optional, Annotated, Literal, Any
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings
import inspect
from pathlib import Path, PurePath


class ExternalSubClass(BaseModel):
    test: Any
    test_simple_list: List[str]
    test_simple_dict: Dict[int, str]


class TestConfig(BaseSettings):
    simple: Any
    log_level: Literal["INFO", "DEBUG"] = "INFO"
    storage_dir: str = Field(
        title="storage for the application state",
        description="A directory to story any states for the bot. Only for saving encryption keys/state at the moment.",
        default_factory=lambda: str(Path(PurePath(Path().home(), ".config/onbot/"))),
    )
    storage_encryption_key: Annotated[
        Optional[str],
        Field(
            description="A passphrase that will be used to encrypt end to end encryption keys https://github.com/poljar/matrix-nio/blob/2632a72e7acee401c4354646a40f31db04db4258/nio/client/base_client.py#L145"
        ),
    ] = None
    constraint_val: Annotated[
        Optional[str],
        Field(
            description="A passphrase that will be used to encrypt end to end encryption keys https://github.com/poljar/matrix-nio/blob/2632a72e7acee401c4354646a40f31db04db4258/nio/client/base_client.py#L145",
            max_length=128,
        ),
    ] = None

    class SynapseServer(BaseModel):
        server_name: Annotated[
            str,
            Field(
                description=inspect.cleandoc(
                    """Synapse's public facing domain https://matrix-org.github.io/synapse/latest/usage/configuration/config_documentation.html#server_name 
                    This is not necessarily the domain under which the Synapse server is reachable. See the docs and your configuration."""
                ),
                example="company.org",
                examples=["company.org", "orga.com"],
            ),
        ]
        tls_enabled: Annotated[
            bool,
            Field(
                title="Secure tls com",
                description="Make any conenciton encrpyted",
                examples=[True, False],
            ),
        ] = False

    synapse_server: Annotated[
        SynapseServer,
        Field(
            title="Synapse Server Configuration",
            description="To manage users on the Synapse server, the bot need access to the Matrix and Admin Api. The authorization data will be configured in this chapter.",
            examples=[SynapseServer(server_name="myservername.om", tls=True)],
        ),
    ]
    external_subconfig: ExternalSubClass
    external_subconfig_list: List[ExternalSubClass]
    external_subconfig_list2: list
    external_subconfig_list_with_eg: Annotated[
        List[ExternalSubClass],
        Field(
            title="A field with an example",
            description="Some nice text",
            examples=[
                [
                    ExternalSubClass(
                        test="a value",
                        test_simple_list=["a", "b", "c"],
                        test_simple_dict={1: "a"},
                    )
                ],
            ],
        ),
    ]

    external_subconfig_dict: Dict[str, ExternalSubClass]
    external_subconfig_dict2: dict
    external_subconfig_dict_with_eg: Annotated[
        Dict[str, ExternalSubClass],
        Field(
            title="A dict field with example",
            examples=[
                {
                    "a": ExternalSubClass(
                        test="a value",
                        test_simple_list=["a", "b", "c"],
                        test_simple_dict={1: "a"},
                    )
                },
            ],
        ),
    ]
