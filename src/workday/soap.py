# -*- coding: utf-8 -*-
# Licensed to Anthony Shaw (anthonyshaw@apache.org) under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import zeep
import zeep.exceptions
import zeep.transports

from .exceptions import WorkdaySoapApiError


class WorkdayResponse(object):
    """
    Response from the Workday API
    """

    def __init__(self, response, service, method, called_args, called_kwargs):
        """
        :param response: The response from the API
        :type  response: ``dict``
        :param service: The web service that was callled
        :type  service: :class:`zeep.proxy.ServiceProxy`
        :param method: The name of the web method called
        :type  method: ``str``
        :param called_args: The arguments that were used to call the method
        :type  called_args: ``list``
        :param called_kwargs: The keyword-arguments that were used to call the method
        :type  called_kwargs: ``dict``
        """
        self.service = service
        self.method = method
        self.called_args = called_args
        self.called_kwargs = called_kwargs
        self._response = response
        if not isinstance(self._response, list):
            if isinstance(self._response["Response_Results"], list) and len(self._response["Response_Results"]) == 1:
              self._response["Response_Results"] = self._response['Response_Results'][0]
            if isinstance(self._response["Response_Filter"], list) and len(self._response["Response_Filter"]) == 1:
                self._response["Response_Filter"] = self._response['Response_Filter'][0]
            elif isinstance(self._response["Response_Filter"], list) and self._response["Response_Filter"] == '[]':
                self._response["Response_Filter"] = ''

    def __iter__(self):
        return self


    def __next__(self):
        """
        Use the iterator protocol as a way of returning paged
        result sets
        """
        if self.method == 'Get_Workers' or self.method == 'Get_Change_Work_Contact_Information':
            if "Response_Filter" in self.called_kwargs:
                if "Page" in self.called_kwargs["Response_Filter"]:
                    if (self.called_kwargs["Response_Filter"]["Page"] == self.total_pages):
                        raise StopIteration
                    else:
                        self.called_kwargs["Response_Filter"]["Page"] += 1
                else:
                    self.called_kwargs["Response_Filter"] = {"Page": 1}
            else:
                self.called_kwargs["Response_Filter"] = {"Page": 1}

        result = getattr(self.service, self.method)(
            *self.called_args, **self.called_kwargs
        )

        return WorkdayResponse(
            result,
            service=self.service,
            method=self.method,
            called_args=self.called_args,
            called_kwargs=self.called_kwargs,
        )

    def next(self):
        return self.__next__()

    @property
    def references(self):
        return self._response.get("Request_References", None)

    @property
    def filter(self):
        if isinstance(self._response["Response_Filter"], list) and len(self._response["Response_Results"]) == 1:
            self._response["Response_Filter"] = self._response['Response_Filter'][0]
        elif isinstance(self._response["Response_Filter"], list):
            self._response["Response_Filter"] = dict()
        return self._response["Response_Filter"]

    @property
    def total_results(self):
          return int(self._response["Response_Results"]["Total_Results"])

    @property
    def total_pages(self):
        return int(self._response["Response_Results"]["Total_Pages"])

    @property
    def page_results(self):
        return int(self._response["Response_Results"]["Page_Results"])

    @property
    def page(self):
        return int(self._response["Response_Results"]["Page"])

    @property
    def data(self):
        return self._response["Response_Data"]

    @property
    def custom_data(self):
        return self._response


class BaseSoapApiClient(object):
    def __init__(self, name, session, wsdl_url, authentication, proxy_url=None):

        """
        :param name: Name of this API
        :type  name: ``str``
        :param session: HTTP session to use for communication
        :type  session: :class:`requests.Session`
        :param wsdl_url: Path to the WSDL
        :type  wsdl_url: ``str``
        :param authentication: Authentication configuration
        :type  authentication: :class:`workday.auth.BaseAuthentication`
        :param proxy_url: (Optional) HTTP Proxy URL
        :type  proxy_url: ``str``
        """
        auth_kwargs = authentication.kwargs
        self._client = zeep.Client(
            wsdl=wsdl_url,
            transport=zeep.transports.Transport(session=session),
            **auth_kwargs
        )

    def __getattr__(self, attr):
        """
        Wrapper around the SOAP client service methods.
        Converts responses to a :class:`WorkdayResponse` instance
        :rtype: :class:`WorkdayResponse`
        """

        def call_soap_method(*args, **kwargs):
            if attr == 'Get_Workers':
                kwargs["Response_Group"] = {"Include_Multiple_Managers_in_Management_Chain_Data": 1, "Include_Personal_Information":1, "Include_Reference":1, "Include_Organizations":1, "Include_Management_Chain_Data":1, "Include_Employment_Information":1, "Include_Roles":1}
            try:
                result = getattr(self._client.service, attr)(*args, **kwargs)
                return WorkdayResponse(
                    result,
                    service=self._client.service,
                    method=attr,
                    called_args=args,
                    called_kwargs=kwargs,
                )
            except zeep.exceptions.Fault as fault:
                raise WorkdaySoapApiError(fault)

        return call_soap_method
