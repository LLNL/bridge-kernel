# Copyright 2019 Lawrence Livermore National Security, LLC and other
# Bridge Kernel Project Developers. See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import print_function, unicode_literals, absolute_import

from IPython.display import display as ipydisplay, Image
from ipykernel.ipkernel import IPythonKernel
from ipywidgets import widgets
import importlib
import base64

from .client import SocketClient, get_backend_list


class BridgeKernel(IPythonKernel):
    banner = "Bridge Kernel"

    def __init__(self, klass=SocketClient, **kwargs):
        assert(issubclass(klass, SocketClient))
        IPythonKernel.__init__(self, **kwargs)
        self.klass = klass
        self.client = None
        # self.execution_count doesn't update
        self.exe_count = 0
        self.magics = {
            "%connect": self.connect_magic,
            "%disconnect": lambda args: self.disconnect()
        }

    def out(self, name, message, silent=False):
        if silent: return
        self.send_response(self.iopub_socket, "stream", dict(name=name, text=message))

    def stdout(self, *args, **kwargs):
        self.out("stdout", *args, **kwargs)

    def stderr(self, *args, **kwargs):
        self.out("stderr", *args, **kwargs)

    def display(self, msg):
        cond = ("module" in msg and
                "attr" in msg and
                "args" in msg)

        if cond:
            try:
                # ModuleNotFoundError
                mod = importlib.import_module(msg["module"])
                args = msg["args"]
                if "decode_bytes" in msg:
                    for key in msg["decode_bytes"]:
                        args[key] = base64.decodebytes(args[key].encode("ascii"))

                # AttributeError
                cb = getattr(mod, msg["attr"])
                if isinstance(args, list):
                    obj = cb(*args)
                elif isinstance(args, dict):
                    obj = cb(**args)
                else:
                    self.stderr("display warning: 'args' is not list or dict")
                    return
                ipydisplay(obj)
            except Exception as e:
                self.stderr("display error: %s" % e)
        else:
            self.stderr("display error: message must contain 'module', 'attr', and 'args'")

    def disconnect(self):
        if self.client is not None:
            self.client.disconnect()
            self.client = None

    def connect(self, cfg):
        if self.client is not None:
            self.disconnect()

        self.config_data = cfg

        self.client = self.klass.from_config(cfg, stdout=self.stdout,
                stderr=self.stderr, display=self.display)

        is_connected = self.client.is_connected

        if is_connected:
            self.client.set_disconnect_callback(self.disconnect)
            print("to disconnect: %disconnect")
        else:
            self.client.disconnect()
            self.client = None
            self.stderr("unable to connect\n")
            return 1

        return 0

    def connect_magic(self, args):
        if self.client is not None:
            print("already connected to backend")
            return

        w = self.pick_backend()

        if w is None:
            self.stdout("no backends available")
        else:
            ipydisplay(w)

    def pick_backend(self):
        backends = get_backend_list()
        fields_to_display = ["codename", "date", "protocol", "argv"]

        if backends is None or len(backends) == 0:
            return None

        names = sorted(list(backends.keys()))
        select = widgets.Dropdown(options=names, value=names[len(names) - 1])
        button = widgets.Button(description="Connect")

        max_len = 0
        for f in fields_to_display:
            if len(f) > max_len:
                max_len = len(f)

        # setup labels to display fields from `fields_to_display`
        label_hboxes = []
        dynamic_labels = {}
        for f in fields_to_display:
            static_label = widgets.Label(value="{} :".format(f))
            dynamic_label = widgets.Label(value="")
            dynamic_labels[f] = dynamic_label
            label_hboxes.append(widgets.HBox([static_label, dynamic_label]))

        # callback when changing the dropdown
        def update_dynamic_labels(elem):
            obj = backends[select.value]
            for f in fields_to_display:
                dynamic_labels[f].value = obj[f]

        update_dynamic_labels(None)
        select.observe(update_dynamic_labels)

        def cb(elem):
            obj = backends[select.value]
            self.connect(obj)
        button.on_click(cb)

        # order the widgets
        widgs = [select]
        widgs.extend(label_hboxes)
        widgs.append(button)

        # when this function is called the widget is displayed
        return widgets.VBox(widgs)

    def do_execute(self, code, silent, store_history=True, user_expressions=None, allow_stdin=False):
        arg0 = code.strip().split(" ")[0]
        if arg0 in self.magics.keys():
            self.magics[arg0](code)
        elif self.client is not None:
            self.client.execute(code)
            self.exe_count += 1
        else:
            self.stdout("no backend - use %connect\n", silent)

        return dict(status="ok", execution_count=self.exe_count, user_expression={})

    def do_complete(self, code, cursor_pos):
        cursor_start = 0
        cursor_end = 0

        # builtins
        first_word = code.split(" ")[0]
        matches = [m for m in self.magics.keys() if first_word != "" and m.find(first_word) == 0]
        if len(matches) > 0:
            cursor_end = cursor_pos
        elif self.client is not None:
            data = self.client.complete(code, cursor_pos)
            if data is not None:
                matches = data["matches"]
                cursor_start = data["cursor_start"]
                cursor_end = data["cursor_end"]

        return dict(matches=matches, cursor_start=cursor_start, cursor_end=cursor_end,
                metadata=None, status="ok")

    def do_shutdown(self, restart):
        self.disconnect()
        return {"restart": False}


if __name__ == "__main__":
    from ipykernel.kernelapp import IPKernelApp
    IPKernelApp.launch_instance(kernel_class=BridgeKernel)
