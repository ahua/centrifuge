# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

import six
import uuid
import tornado.web
import tornado.escape
import tornado.auth
import tornado.httpclient
import tornado.gen
from tornado.gen import coroutine, Return
from tornado.web import decode_signed_value
from sockjs.tornado import SockJSConnection

import centrifuge
from centrifuge.log import logger
from centrifuge.utils import json_encode, json_decode
from centrifuge.handlers import BaseHandler


class WebBaseHandler(BaseHandler):

    def get_current_user(self):
        user = self.get_secure_cookie("user")
        if not user:
            return None
        return user


class LogoutHandler(WebBaseHandler):

    def get(self):
        self.clear_cookie("user")
        self.redirect(self.reverse_url("main"))


class AuthHandler(WebBaseHandler):

    def authorize(self):
        self.set_secure_cookie("user", "authorized")
        next_url = self.get_argument("next", None)
        if next_url:
            self.redirect(next_url)
        else:
            self.redirect(self.reverse_url("main"))

    def get(self):
        if not self.opts.get("password"):
            self.authorize()
        else:
            self.render('index.html')

    def post(self):
        password = self.get_argument("password", None)
        if password and password == self.opts.get("password"):
            self.authorize()
        else:
            self.render('index.html')


class MainHandler(WebBaseHandler):

    @tornado.web.authenticated
    @coroutine
    def get(self):
        """
        Render main template with additional data.
        """
        user = self.current_user.decode()

        projects, error = yield self.application.structure.project_list()
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))

        config = self.application.settings.get('config', {})
        metrics_interval = config.get('metrics', {}).get('interval', self.application.METRICS_EXPORT_INTERVAL)*1000

        context = {
            'js_data': tornado.escape.json_encode({
                'current_user': user,
                'socket_url': '/socket',
                'projects': projects,
                'metrics_interval': metrics_interval
            }),
            'centrifuge_version': centrifuge.__version__,
            'node_count': len(self.application.nodes) + 1,
            'engine': getattr(self.application.engine, 'NAME', 'unknown'),
            'structure': getattr(self.application.structure.storage, 'NAME', 'unknown'),
            'node_name': self.application.name
        }
        self.render("main.html", **context)


def params_from_request(request):
    return dict((k, ''.join([x.decode('utf-8') for x in v])) for k, v in six.iteritems(request.arguments))


class ProjectDetailHandler(WebBaseHandler):

    @coroutine
    def get_project(self, project_id):
        project, error = yield self.application.structure.get_project_by_id(project_id)
        if not project:
            raise tornado.web.HTTPError(404)
        raise Return((project, None))

    @coroutine
    def get_credentials(self):
        data = {
            'user': self.current_user,
            'project': self.project,
        }
        raise Return((data, None))

    @coroutine
    def get_actions(self):
        data, error = yield self.get_credentials()
        raise Return((data, None))

    @coroutine
    def post_actions(self):
        params = params_from_request(self.request)
        method = params.pop('method')
        params.pop('_xsrf')
        data = params.get('data', None)
        if data is not None:
            try:
                data = json_decode(data)
            except Exception as e:
                logger.error(e)
            else:
                params["data"] = data

        result, error = yield self.application.process_call(self.project, method, params)

        self.set_header("Content-Type", "application/json")
        self.finish(json_encode({
            "body": result,
            "error": error
        }))

    @tornado.web.authenticated
    @coroutine
    def get(self, project_name, section):

        self.project, error = yield self.get_project(project_name)

        if section == 'credentials':
            template_name = 'project/detail_credentials.html'
            func = self.get_credentials

        elif section == 'actions':
            template_name = 'project/detail_actions.html'
            func = self.get_actions

        else:
            raise tornado.web.HTTPError(404)

        data, error = yield func()

        self.render(template_name, **data)

    @tornado.web.authenticated
    @coroutine
    def post(self, project_name, section):
        self.project, error = yield self.get_project(
            project_name
        )
        if section == 'actions':
            yield self.post_actions()
        else:
            raise tornado.web.HTTPError(404)


class AdminSocketHandler(SockJSConnection):

    @coroutine
    def subscribe(self):
        self.uid = uuid.uuid4().hex
        self.application.add_admin_connection(self.uid, self)
        logger.info('admin connected')

    def unsubscribe(self):
        if not hasattr(self, 'uid'):
            return
        self.application.remove_admin_connection(self.uid)
        logger.info('admin disconnected')

    def on_open(self, info):
        try:
            value = info.cookies['user'].value
        except (KeyError, AttributeError):
            self.close()
        else:
            user = decode_signed_value(
                self.application.settings['cookie_secret'], 'user', value
            )
            if user:
                self.subscribe()
            else:
                self.close()

    def on_close(self):
        self.unsubscribe()


class Http404Handler(WebBaseHandler):

    def get(self):
        self.render("http404.html")


class StructureDumpHandler(WebBaseHandler):

    @tornado.web.authenticated
    @coroutine
    def get(self):
        data = self.application.structure
        self.set_header("Content-Type", "application/json")
        self.finish(json_encode(data))
