from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional

from langchain_core.outputs import GenerationChunk
from langchain_core.pydantic_v1 import BaseModel, Field, root_validator

from langchain.callbacks.manager import (
    CallbackManagerForLLMRun
)
from langchain.llms.base import LLM
from langchain.utils import get_from_dict_or_env


class VolcEngineMaasBase(BaseModel):
    """Base class for VolcEngineMaas models."""
    client: Any

    volc_engine_maas_ak: Optional[str] = None
    """access key for volc engine"""
    volc_engine_maas_sk: Optional[str] = None
    """secret key for volc engine"""

    endpoint: Optional[str] = "maas-api.ml-platform-cn-beijing.volces.com"
    """Endpoint of the VolcEngineMaas LLM."""

    region: Optional[str] = "Region"
    """Region of the VolcEngineMaas LLM."""

    model: str = "skylark-lite-public"
    """Model name. you could check this model details here https://www.volcengine.com/docs/82379/1133187
    and you could choose other models by change this field"""
    model_version: Optional[str] = None
    """Model version. Only used in moonshot large language model. you could check details here https://www.volcengine.com/docs/82379/1158281"""

    top_p: Optional[float] = 0.8
    """Total probability mass of tokens to consider at each step."""

    temperature: Optional[float] = 0.95
    """A non-negative float that tunes the degree of randomness in generation."""

    model_kwargs: Dict[str, Any] = Field(default_factory=dict)
    """model special arguments, you could check detail on model page"""

    streaming: bool = False
    """Whether to stream the results."""

    connect_timeout: Optional[int] = 60
    """Timeout for connect to volc engine maas endpoint. Default is 60 seconds."""

    read_timeout: Optional[int] = 60
    """Timeout for read response from volc engine maas endpoint. Default is 60 seconds."""

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        ak = get_from_dict_or_env(values,"volc_engine_maas_ak","VOLC_ACCESSKEY")
        sk = get_from_dict_or_env(values,"volc_engine_maas_sk","VOLC_SECRETKEY")
        endpoint = values["endpoint"]
        if values["endpoint"] is not None and values["endpoint"] != "":
            endpoint = values["endpoint"]
        try:
            from volcengine.maas import MaasService, ChatRole

            maas = MaasService(endpoint,
                               values["region"],
                               connection_timeout=values["connect_timeout"],
                               socket_timeout=values["read_timeout"])
            maas.set_ak(ak)
            values["volc_engine_maas_ak"] = ak
            values["volc_engine_maas_sk"] = sk
            maas.set_sk(sk)
            values["client"] = maas
        except ImportError:
            raise ImportError(
                "volcengine package not found, please install it with "
                "`pip install volcengine`"
            )
        return values

    @property
    def _default_params(self) -> Dict[str, Any]:
        """Get the default parameters for calling VolcEngineMaas API."""
        normal_params = {
            "top_p": self.top_p,
            "temperature": self.temperature,
        }

        return {**normal_params, **self.model_kwargs}


class VolcEngineMaasLLM(LLM, VolcEngineMaasBase):
    """volc engine maas hosts a plethora of models. You can utilize these models through this class.

    To use, you should have the ``volcengine`` python package installed.
    and set access key and secret key by environment variable or direct pass those to this class.
    access key, secret key are required parameters which you could get help https://www.volcengine.com/docs/6291/65568

    In order to use them, it is necessary to install the 'volcengine' Python package.
    The access key and secret key must be set either via environment variables or passed directly to this class.
    access key and secret key are mandatory parameters for which assistance can be sought at https://www.volcengine.com/docs/6291/65568.

    Example:
        .. code-block:: python

            from langchain.llms import VolcEngineMaasLLM
            model = VolcEngineMaasLLM(model="skylark-lite-public",
                                          volc_engine_maas_ak="your_ak",
                                          volc_engine_maas_sk="your_sk")
    """

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "volc-engine-maas-llm"

    def _convert_prompt_msg_params(
            self,
            prompt: str,
            **kwargs: Any,
    ) -> dict:
        model_req = {
            "model": {
                "name": self.model,
            }
        }
        if self.model_version is not None:
            model_req["model"]["version"] = self.model_version

        return {
            **model_req,
            "messages": [{
                "role": "user",
                "content": prompt
            }],
            "parameters": {**self._default_params, **kwargs},
        }

    def _call(
            self,
            prompt: str,
            stop: Optional[List[str]] = None,
            run_manager: Optional[CallbackManagerForLLMRun] = None,
            **kwargs: Any,
    ) -> str:
        if self.streaming:
            completion = ""
            for chunk in self._stream(prompt, stop, run_manager, **kwargs):
                completion += chunk.text
            return completion
        params = self._convert_prompt_msg_params(prompt, **kwargs)
        response = self.client.chat(params)

        return response.get("choice", {}).get("message", {}).get("content", "")

    def _stream(
            self,
            prompt: str,
            stop: Optional[List[str]] = None,
            run_manager: Optional[CallbackManagerForLLMRun] = None,
            **kwargs: Any,
    ) -> Iterator[GenerationChunk]:
        params = self._convert_prompt_msg_params(prompt, **kwargs)
        for res in self.client.stream_chat(params):
            if res:
                chunk = GenerationChunk(text=res.get("choice", {}).get("message", {}).get("content", ""))
                yield chunk
                if run_manager:
                    run_manager.on_llm_new_token(chunk.text, chunk=chunk)
