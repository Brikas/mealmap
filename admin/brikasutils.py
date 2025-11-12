from time import sleep
from time import time
import csv
import os
import sys
import io
import traceback
from typing import List, Optional, Callable, TypedDict, Union
import asyncio
import aiohttp
from typing import Protocol, runtime_checkable, Any
import copy

import requests

__version__ = "2025-06-22"

def gpt(text, gpt4: bool = True, return_full_response: bool = False, api_key = None, model=None, context = []):
    import requests
    import json

    if api_key is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key is None:
            raise Exception("OPENAI_API_KEY environment variable not set")
        
    if model is not None:
        model_final = model
    elif gpt4:
        model_final = "gpt-4"
    else:
        model_final = "gpt-3.5-turbo"
        
    
    HEADERS = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    ENDPOINT = "https://api.openai.com/v1/chat/completions"
    SETTINGS = {
        "model": model_final,
        "temperature": 0.7,
    }

    data = {
        "messages": [ *context ,{"role": "user", "content": text}],
        **SETTINGS,
    }

    response = requests.post(ENDPOINT, headers=HEADERS, data=json.dumps(data))

    try:
        if return_full_response:
            return response.json()
        return response.json()['choices'][0]['message']['content']
    except KeyError as e:
        print(response.json())
        # throw error with reponse
        raise Exception(response.json())
    
def clean(input_str, line_and_tabs=False ,remove_non_printable=False) -> str:
    """
    Cleans a string
    1. Removes leading/trailing
    2. Removed double spaces
    3. Removes control
    4. [OPTIONAL] Removed line and tab breakss
    5. [OPTIONAL] Removes all non printable (spaces, tabs, etc.)
    """
    import unicodedata
    import re
    
    if input_str == None: return ""

    input_str = ''.join(c for c in input_str if not unicodedata.category(c).startswith('C')) 

    if remove_non_printable:
        allowed_categories = {'Lu', 'Ll', # lower upper cae letters
            'Nd', #  1 2 digits
            "Pd" # , . : 
        }
        return ''.join(c for c in input_str if unicodedata.category(c) in allowed_categories)
    
    if line_and_tabs:
        to_replace = ["\r","\n","\t"]
        for i in to_replace:
            input_str = input_str.replace(i, '')

    input_str = input_str.strip()
    input_str = re.sub(r' {2,}' , ' ', input_str) # Double spaces
    # Control

    return input_str

def dict_trim(dictionary, start = 0, end = 0):
    return dict(list(dictionary.items())[start:end])

def get_timestamp():
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")

def make_filename_safe(str_input, remove_dir_separators = False):
    txt = "".join([c for c in str_input if c.isalpha() or c.isdigit() or c=="_" or c==' ' or c == "/" or c == "\\" or c == "-"]).rstrip()
    # src: https://stackoverflow.com/questions/7406102/create-sane-safe-filename-from-any-unsafe-string

    if remove_dir_separators:
        txt = txt.replace("/", "")
        txt = txt.replace("\\", "")
    
    return txt

def if_dir_not_exist_make(path):
    import os
    if path is None or path == "": return
    if not os.path.exists(path): os.makedirs(path)

def quickJSON(dictionary, filename=""):
    import json

    if filename == "":
        filename = "quickJSON" + get_timestamp() + ".json"

    with open(filename, 'w') as fp:
        json.dump(dictionary, fp, indent=4)

def quickTXT(data, filename=""):
    if (filename == ""):
        filename = "quickTXT_" + get_timestamp() + ".txt"
    with open(filename, 'w', encoding="UTF16") as fp:

        if isinstance(data, list):
            fp.write('\n'.join(data) + '\n')
            return

        fp.write(data)

def quickCSV(rows, filename=None, headers = None, delimiter=",", quotechar = '"', encoding = "utf-16", verbose = True):
    """
    param: rows - the list of rows which to write.
    
    optional param: filename - filename. If equal to None, then quickCSV_timestamp.csv

    Rows is an iterable (list).
    """
    import csv
    import sys

    if (filename == None):
        filename = "quickCSV_" + get_timestamp() + ".csv"

    if sys.version_info >= (3,0,0):
        f = open(filename, 'w', newline='', encoding=encoding)
    else:
        f = open(filename, 'wb')

    csv_writer = csv.writer(f, delimiter=delimiter, quotechar=quotechar, quoting=csv.QUOTE_MINIMAL)

    if headers is not None:
        csv_writer.writerow(headers)
    for row in rows:
        csv_writer.writerow(row)

    f.close()

    if verbose:
        print(f"brikasutils.quickCSV: Saved {len(rows)} as {filename}")


def join_tables(rows1: list, headers1: list, rows2: list, headers2: list, join = "outer"):
    """
    Returns tuple (headers, rows)

    param: join - outer or inner (default outer)
    """
    import pandas as pd
    df1 = pd.DataFrame(rows1, columns=headers1)
    df2 = pd.DataFrame(rows2, columns=headers2)

    # Duplicate column handling
    duplicate_column_map = df1.columns.duplicated()
    if True in duplicate_column_map:
        print(f"[WARNING] {join_tables.__name__} found duplicate columns (headers1). Keeping only the first ones.")
        df1 = df1.loc[:,~duplicate_column_map].copy()
    duplicate_column_map = df2.columns.duplicated()
    if True in duplicate_column_map:
        print(f"[WARNING] {join_tables.__name__} found duplicate columns (headers2). Keeping only the first ones.")
        df2 = df2.loc[:,~duplicate_column_map].copy()


    result = pd.concat([df1, df2], axis=0, join=join, ignore_index=True)
    result.fillna('', inplace=True)
    
    headers = result.columns.to_list()
    rows = result.values.tolist()

    return (headers, rows)

def mute(f):
    """
    Can be used as a decorator. Disabled console output.
    """
    def wrapper(*args, **kwargs):
        import sys
        original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')
        f(*args, **kwargs)
        sys.stdout.close()
        sys.stdout = original_stdout
    
    return wrapper

class MutePrint:
    """
    Usage:
    with MutePrint():
        print("This will not be shown.")

    print("This will be shown.")
    """

    def __enter__(self):
        
        self.original_stdout = sys.stdout
        sys.stdout = io.StringIO()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout = self.original_stdout


def remove_duplicates_list_of_lists(list_of_lists) -> list:
    """
    Preserved order
    """
    from itertools import filterfalse, tee
    def unique_everseen(iterable, key=None):
        #List unique elements in order of first appearance. 
        # If key is not None, use key to specify uniqueness.
        seen = set()
        seen_add = seen.add
        if key is None:
            for element in filterfalse(seen.__contains__, iterable):
                seen_add(element)
                yield element
        else:
            for element in iterable:
                k = key(element)
                if k not in seen:
                    seen_add(k)
                    yield element

    new_list = list(unique_everseen(list_of_lists, key=lambda x: tuple(x)))
    return new_list

def convert_dicts_to_table(list_of_dicts, forced_fieldnames = None, expand_fieldnames = True, expanded_fieldnames_output_obj = None):
    """
    Conversa list of dicts to a table. 

    param: list_of dicts - i.e. [{"name": "John, "surname": "Miller"}, {"surname": "Tames"}]
    param: insert_fieldnames -  bool, whether to insert the column headers as row 0. Disable for append purposes.
    param: foreced_fieldnames - force the given fieldnames to be in the column list, even if no data have them.
                                this is also a way to enforce the sequence of fieldnames
    param: expand_forced_fieldnames - if forced fieldnames are used, then if True, newfound fieldnames will be
                                        also appended as columns.

    returns: tuple with [0] - headers, [1] - rows
    return obj: expanded_fieldnames_output_obj - if a list is given, then that list is updated with new expanded fieldnames.
    """
    # OPTIMIZATION POSSIBILITY: dynamically add columns as new column is encountered, so only 1 loop is used.
    is_forced_provided = False if forced_fieldnames is None else True
    fieldnames = forced_fieldnames if is_forced_provided else [] # If forced is not provided, then make new list

    # Get all fieldnames
    if expand_fieldnames:
        for entry in list_of_dicts:
            for key in entry.keys():
                if key not in fieldnames:
                    fieldnames.append(key)
                    if expanded_fieldnames_output_obj is not None: expanded_fieldnames_output_obj.append(key)


    # Convert entries (dicts) to a 2D array (list of lists)
    rows = [[item.get(key, '') for key in fieldnames] for item in list_of_dicts]
    
    return (fieldnames, rows)


class RequestTemplate(aiohttp.client._RequestOptions, total=False):
    """
    RequestTemplate as a TypedDict for run_async_requests. 
    """
    method: str
    url: str
    callback: Optional["RequestCallback"]
    timeout: Union[aiohttp.ClientTimeout, aiohttp.helpers._SENTINEL, int, None]
    params: dict[str, Any]
    session: Optional[aiohttp.ClientSession]

class AsyncSharedProgress:
    def __init__(self, lock: asyncio.Lock):
        self._completed = 0
        self._total = 0
        self.lock = lock

    def increment_completed(self):
        self._completed += 1

    def increment_total(self):
        self._total += 1

    @property
    def completed_count(self) -> int:
        return self._completed
    
    @property
    def total_count(self) -> int:
        return self._total

class CustomResponse:
    """
    CustomResponse is a simple response wrapper class that mimics the interface of HTTP response objects.
    """

    status: int
    """The HTTP status code of the response."""
    
    status_code: int
    """Alias for status, for compatibility with some HTTP libraries."""
    
    json_data: Optional[dict]
    """The JSON data returned by the response, if any. Same as .json() method."""
    
    text_data: Optional[str]
    """The plain text data returned by the response, if any."""

    raw_response: Optional[aiohttp.ClientResponse]
    """The raw aiohttp.ClientResponse object. It may be none if the operation failed before the request was sent (internal error)."""

    def __init__(self, status: int, request_template: RequestTemplate, shared_async_progress: AsyncSharedProgress, raw_response: aiohttp.ClientResponse | None, json_data: Optional[dict] = None, text_data: Optional[str] = None, index: int = 1):
        self.status = status
        self.status_code = self.status
        self.text_data = text_data
        self.json_data = json_data
        self.raw_response = raw_response
        self._request_template = request_template
        self.index = index
        self.shared_async_progress = shared_async_progress

    # getter
    def get_request_template(self, do_copy: bool = True, deep_copy: bool = False) -> RequestTemplate:
        """
        Returns a copy of the request template used to generate this response.

        Args:
            do_copy (bool): If True, returns a copy of the request template. If False, returns the refference to the original template. Be careful setting this to false, as modifying the original template will affect all responses that use it.
            deep_copy (bool): If True, performs a deep copy of the request template. Will throw an error is set to false.
        """
        if not do_copy:
            if deep_copy:
                raise ValueError("Cannot use deep_copy without do_copy=True. Set do_copy=True to enable deep copy.")
            return self._request_template
        
        if do_copy:
            if deep_copy:
                try:
                    return copy.deepcopy(self._request_template)
                except Exception as e:
                    raise ValueError(f"Failed to deepcopy request_template. Try setting the deep_copy to False. Error: {e}") from e
            else:
                return copy.copy(self._request_template)
    
    def json(self) -> Optional[dict]:
        """
        Returns the JSON data of the response.

        Alias for the `json_data` attribute.
        """
        return self.json_data
    
    
    def get_request_template_copy_with(self, deep_copy = False, **kwargs) -> RequestTemplate:
        """
        Returns a copy of the request template with updated parameters.

        Useful for modifying the request template after the response has been received.
        """
        new_template = self.get_request_template(do_copy=True, deep_copy=deep_copy)
        for key, value in kwargs.items():
            setattr(new_template, key, value)
        return new_template
    
    def get_request_template_copy_with_updated_params(self, params_update, deep_copy = False, **kwargs) -> RequestTemplate:
        """
        Returns a copy of the request template with updated parameters, appending new params and replacing existing.

        Useful for modifying the request template after the response has been received, esp. for recursive pagination.
        """
        new_template = self.get_request_template_copy_with(deep_copy=deep_copy, **kwargs)
        new_template.setdefault('params',{}).update(params_update)
        return new_template

    @property
    def text(self) -> Optional[str]:
        return self.text_data
    


@runtime_checkable
class RequestCallback(Protocol):
    """
    A callback function for async requests.

    Must accept at least:
        - response: CustomResponse
    
    May have any other **kwargs.

    Should return:
        - None, or a list of RequestTemplate objects to schedule.
    """    
    def __call__(
        self,
        response: CustomResponse,
    ) -> Optional[Union[RequestTemplate, List[RequestTemplate], None]]:
        ... # No implementation needed, just a protocol for type checking



        

def run_async_requests(request_templates: List[RequestTemplate], max_concurrent = 15, verbose=True, session = None, show_full_error=False) -> List[CustomResponse]:
    """
    Runs multiple HTTP requests asynchronously based on provided templates and returns the results.

    This function supports both initial requests and dynamically scheduled requests via callbacks. To dynamically schedule requests, return a list of new RequestTemplate objects from the callback function.

    - Initial requests are returned in the same order as provided.
    - If a callback returns new requests, those are scheduled and their results are appended (order not guaranteed).

    CustomResponse objects contain a copy of request template. It can be useful inside the callback to modify the request template for subsequent requests.

    Example usage:

        request_templates = [
            RequestTemplate(method="get", url="https://api.example.com/data"),
            RequestTemplate(method="post", url="https://api.example.com/submit", json={"key": "value"})
            RequestTemplate(method="get", url="https://api.example.com/data", headers={"Authorization": "Bearer YOUR_TOKEN"}
            RequestTemplate(
                method="get",
                url="https://api.example.com/data",
                headers={"Authorization": "Bearer YOUR_TOKEN"},
                callback= lambda response: print(response.json()
            ),
            RequestTemplate(
                method = "get",
                url = "https://api.example.com/data?page=1",
                headers = {"Authorization": "Bearer YOUR_TOKEN"},
                callback = lambda response: response.request_template_copy_with_updated_params(
                    params_update={
                        "page": response.json()['current_page'] + 1,
                    }
                )
            )
        ]

    Args:
        request_templates (list[RequestTemplate]): 
            Each template must include:
                - 'method': HTTP method (e.g., 'get', 'post')
                - 'url': Target URL
                - Any aiohttp.ClientSession.request() keyword arguments (e.g., 'headers', 'json', etc.)
                - Optional 'callback': function called with (response: CustomResponse) that can return new RequestTemplate(s) to be scheduled dynamically.

    Returns:
        list[CustomResponse]: List of response objects, in order for initial requests, followed by any dynamically scheduled requests.
    """

    async def run_requests_async(initial_templates):
        lock = asyncio.Lock()
        semaphore = asyncio.Semaphore(max_concurrent)
        queue = asyncio.Queue()
        results: list[Optional[CustomResponse]] = [None] * len(initial_templates)  # Pre-allocate for initial tasks
        dynamic_results: list[CustomResponse] = []  # For tasks added later

        progress = AsyncSharedProgress(lock)

        # Seed the queue
        for i, template in enumerate(initial_templates):
            await queue.put((template, i))

        global_session = session or aiohttp.ClientSession()
        session_is_owner = session is None

        async def worker():
            nonlocal progress
            while True:
                try:
                    template, request_index = await queue.get()
                except asyncio.CancelledError:
                    break
                progress.increment_total()
                try:
                    async with semaphore:
                        # Use per-request session if present, else global
                        req_session = template.get('session') or global_session
                        if requests and isinstance(req_session, requests.Session):
                            raise TypeError(
                                f"""
                                You passed a requests.Session object to an async function!
                                This code only supports aiohttp.ClientSession for async requests.
                                Received: {type(req_session)}
                                
                                Fix: Use aiohttp.ClientSession() instead.
                                """
                            )
                        try:
                            async with req_session.request(template['method'], template['url'],
                                                        **{k: v for k, v in template.items() if k not in ('method', 'url', 'callback', 'session')}) as response:
                                json_data = await response.json(content_type=None) if response.content_type == 'application/json' else None
                                text_data = await response.text()
                                async with lock:
                                    progress.increment_completed()
                                    if verbose:
                                        if response.status >= 400:
                                            print(f"[{progress.completed_count}] Request {request_index + 1} returned {response.status}. {text_data}")
                                        else:
                                            print(f"[{progress.completed_count}] Request {request_index + 1} returned {response.status}.")
                                custom_response = CustomResponse(status=response.status, request_template=template, shared_async_progress=progress, raw_response=response, json_data=json_data, text_data=text_data, index=request_index+1)
                                

                                new_templates = None # Can be one template or multiple templates
                                if template.get('callback'):
                                    try:
                                        new_templates = template['callback'](custom_response) # Can be one template or multiple templates
                                    except Exception as e:
                                        if show_full_error:
                                            print(f"[{progress.completed_count}] Error in callback for request {request_index + 1}: {traceback.format_exc()}")
                                        else:
                                            print(f"Error in callback for request {request_index + 1}: {e}")
                                # Store result in order for initial tasks, append for dynamic
                                if request_index < len(results):
                                    results[request_index] = custom_response
                                else:
                                    dynamic_results.append(custom_response)

                                # If callback returns new template(s), add them to the queue
                                if isinstance(new_templates, dict):
                                    # If a single template is returned, just send it.
                                    await queue.put((new_templates, progress.total_count))

                                if isinstance(new_templates, list):
                                    for t in new_templates:
                                        await queue.put((t, progress.total_count))
                        except Exception as e:
                            async with lock:
                                progress.increment_completed()
                            print(f"[{progress.completed_count}] Request {request_index + 1} failed internally with exception: {traceback.format_exc()}")
                            
                            # Store a failed CustomResponse or None
                            custom_response = CustomResponse(status=999, request_template=template, raw_response=None, json_data=None, text_data=str(e))
                            if request_index < len(results):
                                results[request_index] = custom_response
                            else:
                                dynamic_results.append(custom_response)
                finally:
                    queue.task_done()

        # Start workers
        workers = [asyncio.create_task(worker()) for _ in range(max_concurrent)]
        await queue.join()
        for w in workers:
            w.cancel()
        
        if session_is_owner:
            await global_session.close()

        # Return initial results in order, then dynamic results
        return [r for r in results if r is not None] + dynamic_results

    # Check if we're in a Jupyter environment and fix the event loop
    try:
        loop = asyncio.get_running_loop()
        # Use `nest_asyncio` to allow for nested event loop usage in Jupyter
        import nest_asyncio
        nest_asyncio.apply()
        return loop.run_until_complete(run_requests_async(request_templates))
    except RuntimeError:
        return asyncio.run(run_requests_async(request_templates))


class Benchmarker(object):
    """
    Benchmarker takes any amount of checkpoints entries, consisting of key, and 
    time (defaults to current).
    Add checkpoints by checkpoint(key, time = now).

    For specific benchmarking use mark_start(key), mark_end(key) and get_time(key).

    Important instance variables:

    checkpoints: dict {key: time_start}

    marks: dict {key: [time_start, time_end]}
    """
    UNNAMED_MARK_PREFIX = "process_"
    def __init__(self, time_start = None, checkpoints_ini = {}):
        from collections import OrderedDict
        self.checkpoints = OrderedDict() # {key: [time_start, time_end]}
        self.marks = OrderedDict() # {key: [time_start, time_end]}
        
        self._repeating_keys = {}

        # Starts timeing if not provided by parameter
        if time_start == None: self.time_start = time()

        self._unnamed_mark_count = 0
        self._is_active_switch_mark = False
        self._last_checkpoint_time = self.time_start


        # Add initial checkpoints to the list of checkpoints
        msg = "("
        for key, timemark in checkpoints_ini.items():
            self.checkpoint(key, time_end = timemark, verbose=False)
            msg += f"{key}, "
        if len(checkpoints_ini) > 0:
            print(msg + ") finished before real-time benchmark logging")

    def get_mark_duration_full(self, key):
        """
        Returns the duration of a mark in seconds with many decimal points.
        Use get_time_formatted() or get_time() for convenient output
        """
        missing_end = False
        try:
            self.marks[key][0]
        except:
            print(f"Benchmarker ERROR: mark {key} was never started. Ignoring call.")
            return
        try:
            if self.marks[key][1] == None: missing_end = True
        except:
            missing_end = True

        if missing_end:
            print(f"Benchmarker WARNING: mark {key} was never ended. Taking current time as end time.")
            self.marks[key][1] = time()

        # If the key is a part of the repearing keys, then gets the last one.
        if key in self._repeating_keys:
            key = f"{key}_{self._repeating_keys[key]}"

        mark = self.marks[key]
        return mark[1] - mark[0] # time_end - time_start
    
    def get_mark_duration(self, key):
        """
        Returns the duration of a mark in seconds rounded to three decimal points.
        To return full prescision time use get_time_full().
        """
        return round(self.get_mark_duration_full(key),3)

    def get_mark_duration_formatted(self, key):
        """
        Returns the duration of a mark in seconds formated {:.3f}s.
        """
        return "{:.3f}s".format(self.get_mark_duration_full(key))
    
    def mark_start(self, key):
        """
        Starts counting duration of a new mark.

        Use mark_end() to finish counting and mark_time() to get time.
        """
        if key in self.marks.keys():
            if key not in self._repeating_keys.keys():
                self._repeating_keys[key] = 1
            new_index = self._repeating_keys[key] + 1
            self._repeating_keys[key] = new_index
            key = f"{key}_{new_index}"
            


        self.marks[key] = [time(), None]

    def mark_end(self, key, verbose = True):
        """
        End counting duration of an existing mark.

        Returns rounded duration in seconds.\n \tBy default, also prints formated display.
        Onerror, returns None.
        """
        if key in self._repeating_keys.keys():
            key = f"{key}_{self._repeating_keys[key]}"

        try:
            self.marks[key][0]
        except:
            print(f"Benchmarker ERROR: mark {key} was never started. Ignoring end call.")
            return None

        self.marks[key][1] = time()
        output = self.get_mark_duration(key)
        if verbose:
            print(f"{key} took {output}s")
        return output
    # also retun formated string
    def mark(self):
        """
        Runs mark_start() and mark_end() in a switch way. Uses a generic key name.

        The quickest way to benchmark.
        """
        if self._is_active_switch_mark:
            key_name = Benchmarker.UNNAMED_MARK_PREFIX + str(self._unnamed_mark_count)
            self.mark_end(key_name, verbose=True)
            self._is_active_switch_mark = False
        else:
            self._unnamed_mark_count += 1
            key_name = Benchmarker.UNNAMED_MARK_PREFIX + str(self._unnamed_mark_count)
            self.mark_start(key_name)
            self._is_active_switch_mark = True

    def print_all_mark_times(self):
        for key in self.marks.keys():
            print(f"{key} took {self.get_mark_duration(key)}s")

    ### Checkpoint processing 
    def checkpoint(self, key, time_end = None, verbose = False):
        if time_end == None:
                    time_end = time()
        self.checkpoints[key] = [self._last_checkpoint_time, time_end]
        self._last_checkpoint_time = time_end

        if verbose: print(f"{key} finished here.")

    def get_checkpoint_duration_full(self, key):
        time_start = self.checkpoints[key][0]
        time_end = self.checkpoints[key][1]

        return time_end - time_start

    def get_checkpoint_duration(self, key):
        return round(self.get_checkpoint_duration_full(key),5)
    
    # Predetermined routines
    def print_all_checkpoints(self, time_end = None):
        if time_end == None: time_end = time()
        time_previous = self.time_start
        for key, [start, end] in self.checkpoints.items():
            print("{}: {:.3f}s, (+ {:.3f}s) ".format(key, end - self.time_start,\
                end - time_previous))
            time_previous = end
    def get_total_execution_time(self):
        try:
            time_end
        except: time_end = time()
        return time_end - self.time_start

    def print_total_execution_time(self):
        print("Total execution time {:.3f}s".format(self.get_total_execution_time()))

    def export_csv(self, filename = None, verbose = True):
        marks_list = []
        for name in list(self.marks.keys()):
            marks_list.append({"type": "mark", "name": name, "duration": round(self.get_mark_duration_full(name),6)})
        for name in list(self.checkpoints.keys()):
            marks_list.append({"type": "checkpoint", "name": name, "duration": round(self.get_checkpoint_duration_full(name),6)})

        
        filename = "benchmarker_" + get_timestamp() + ".csv" if filename == None else filename
        headers, rows = convert_dicts_to_table(marks_list)
        table = [headers] + rows
        quickCSV(table, filename=filename)
        if verbose: print("Benchmarket data exported to " + filename)

class LiveCSV():
    """
    Load a CSV file and then dynamically append data to it.

    Features:
    The data appended can have more/less columns.
    The file can be edited and saved in another app in the mean time. It does not keep it open.
    If file was edited in the mean time, LiveCSV preserves the changes made in the meantime.
    Adding to the above, it also preserved the changed column order.
    """
    def __init__(self, filename=None, encoding=None, delimiter=None, quotechar=None):
        self._filename = filename

        self.delimiter = "," if delimiter is None else delimiter
        self.quotechar = '"' if quotechar is None else quotechar
        self.encoding = "utf-8-sig" if encoding is None else encoding
        
        self.fieldnames = None
        self.is_loaded = False

        if self._filename is not None:
            self.load()


    def append_data(self, append_rows, append_fieldnames):
        """
        Updates the table with new data.
        Preserves live column order and data.
        
        """
        if self.is_loaded == False: raise IOError("No file was loaded. use load(filename)")

        table = self._read()
        latest_fieldnames = table[0]
        latest_rows = table[1]

        # columns could be shuffled
        new_fieldnames, new_rows = join_tables(latest_rows, latest_fieldnames, append_rows, append_fieldnames)

        quickCSV(
            new_rows, headers = new_fieldnames, filename=self._filename,
            delimiter = self.delimiter, quotechar=self.quotechar, encoding=self.encoding
        )
        

    def _read(self):
        with open(self._filename, "r", newline='', encoding=self.encoding) as csvfile:
            reader = csv.reader(csvfile, delimiter=self.delimiter, quotechar=self.quotechar)
            # self.fieldnames = next(reader)
            
            try:
                fieldnames = next(reader)
            except:
                fieldnames = []
                
            rows = []
            for row in reader:
                rows.append(row)

        return (fieldnames,rows)


    def load(self, filename=None, encoding=None, delimiter=None, quotechar=None):
        """
        Default delimiter is ,
        Default quatechar is "
        """
        import os
        
        # Uses the param filename as priority. If not provided then checks if it was define beforehand.
        # If both are undefined then gives an error.
        if filename is not None: self._filename = filename
        elif self._filename is None: raise TypeError("Filename not given.")


        if delimiter is not None: self.delimiter = delimiter
        if quotechar is not None: self.quotechar = quotechar
        if encoding is not None: self.encoding = encoding
        try:
            with open(self._filename, "r", newline='', encoding=self.encoding) as csvfile:
                reader = csv.reader(csvfile, delimiter=self.delimiter, quotechar=self.quotechar)

                try:
                    self.fieldnames = next(reader)
                except:
                    self.fieldnames = []
                
                print(f"Recognized {len(self.fieldnames)} headers in {self._filename}")
        except FileNotFoundError:
            print(f"LiveCSV: File {os.path.abspath(self._filename)} not existing. Creating new.")
            return self.create()
        
        self.is_loaded = True


    def create(self, filename=None, data=[], encoding=None, delimiter=None, quotechar=None):

        # Uses the param filename as priority. If not provided then checks if it was define beforehand.
        # If both are undefined then gives an error.
        if filename is not None: self._filename = filename
        elif self._filename is None: raise TypeError("Filename not given.")

        if delimiter is not None: self.delimiter = delimiter
        if quotechar is not None: self.quotechar = quotechar
        if encoding is not None: self.encoding = encoding

        quickCSV(data, filename=self._filename)
        self.is_loaded = True

class FileRunQueue():
    """
    Basic usage:
    queue = FileRunQueue()
    for filepath in queue:
        print(f"Running {filepath}")
        # do something with the file
    """

    def __init__(self, queue_folder_path = "queue", verbose = True, do_move = True, completed_folder_path = None):
        """
        @param queue_folder_path: str - path to the folder where the files are stored.
        @param completed_folder_path: str - path to the folder where the completed files are stored. If None, then it is set to queue_folder_path/done
        @param do_move: bool - if True, then moves the file to the completed folder. If False, then adds the file to done_files.
        """
        

        self.queue_folder_path = queue_folder_path
        self.verbose = verbose
        self._completed = 0
        self._last_file = None
        self.do_move = do_move
        self.done_files = []

        self.completed_folder_path = os.path.join(self.queue_folder_path, "done") if completed_folder_path is None else completed_folder_path
        if_dir_not_exist_make(self.queue_folder_path)
        if_dir_not_exist_make(self.completed_folder_path)

    def __iter__(self):
        return self

    def __next__(self) -> str:
        from os import walk
        if self._last_file is not None:
            self.move_last_file()
            self._last_file = None
            self._completed += 1

        # All files and directories ending with .txt and that don't begin with a dot:
        f = []
        for (dirpath, dirnames, filenames) in walk(self.queue_folder_path):
            f.extend(filenames)
            break
        
        f = [item for item in f if item not in self.done_files] # f - self.done_files

        queue_len = len(f)
        if queue_len > 0:
            next_f = f[0]
            if self.verbose: self.print_info(next_f,queue_len)
            self._last_file = next_f
            return os.path.join(self.queue_folder_path ,next_f)

        raise StopIteration

    def print_info(self, filename, queue_len):
        print(f"[{self._completed+1}/{queue_len + self._completed}] Running {filename} from queue. ")

    def move_last_file(self):
        if self.do_move:
            if self._last_file is None: return

            os.replace(
                os.path.join(self.queue_folder_path, self._last_file),
                os.path.join(self.completed_folder_path, self._last_file)
            )
        else:
            self.done_files.append(self._last_file)

    @staticmethod
    def timed_stop_prompt(timeout = 20) -> bool:
        """
        @returns True if needs to stop, False if needs to continue.
        """
        from inputimeout import inputimeout, TimeoutOccurred
        
        try:
            c = inputimeout(prompt=f'Error encountered. Type anything to quit all. (auto continue in {timeout} s.): ', timeout=timeout)
        # except:
        except TimeoutOccurred:
            print("Auto continueing with next task...")
            return False
        print("Task queue terminated.")
        return True







