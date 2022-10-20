from abc import abstractmethod, ABCMeta
from flow.http.render.render import RenderPage
from flow.database.model.models import QuerySet
from flow.routing.route import RedirectUrl


class View(metaclass=ABCMeta):
    """
    Базове представлення view.
    """
    def __init__(self):
        self.html_page: str = 'Default page.'
        self.template_path = ''
        self.template_obj = {}
        self.request = None
        self.queryset: QuerySet = None

    @abstractmethod
    def post(self) -> RedirectUrl:
        """
        Обробка методу post із html форми.
        """
        pass

    def __call__(self, request, **kwargs) -> str:
        """
        Виконнаня усієї логіки view.
        :param request:
        :param kwargs:
        :return:
        """
        self.request = request
        if 'slug_value' in kwargs.keys():
            self.render(slug_val=kwargs['slug_value'])
        else:
            self.render()
        return self.html_page

    @abstractmethod
    def render(self, **kwargs):
        """
        Виконання основного алгоритму представлення.
        """
        pass


class TemplateView(View):
    """
    Представлення html сторінки з вибраними параметрами.
    """
    def __init__(self):
        super().__init__()
        self.template_path = ''

    def post(self) -> RedirectUrl:
        pass

    def render(self, **kwargs):
        self.html_page = RenderPage(self.template_path).render()
        return self


class ListView(View):
    """
    Представлення списком усіх полів із моделі.
    """
    def __init__(self):
        super(ListView, self).__init__()
        self.model = None
        self.obj_name = ''

    def post(self) -> RedirectUrl:
        pass

    def render(self, **kwargs):
        self.queryset = self.model().db.all()
        self.template_obj[self.obj_name] = self.queryset
        self.html_page = RenderPage(self.template_path).render(**self.template_obj)
        return self


class ObjectView(View):
    """
    Представлення конкретного поля із моделі.
    """
    def __init__(self):
        super(ObjectView, self).__init__()
        self.model = None
        self.obj_name = ''
        self.slug_field = ''

    def post(self) -> RedirectUrl:
        pass

    def render(self, **kwargs):
        self.queryset = self.model().db.get(**{self.slug_field: kwargs['slug_val']})
        self.template_obj[self.obj_name] = self.queryset
        self.html_page = RenderPage(self.template_path).render(**self.template_obj)
        return self
