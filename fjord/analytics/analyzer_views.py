# Note: These views are viewable only by people in the analyzers
# group. They should all have the analyzer_required decorator.
#
# Also, because we have this weird thing with new users,
# they should also have the check_new_user decorator.
#
# Thus each view should be structured like this:
#
#    @check_new_user
#    @analyzer_required
#    def my_view(request):
#        ...
#
# Also, since it's just analyzers, everyone is expected to speak
# English. Ergo, there's no localization here.

from collections import defaultdict
from datetime import date, datetime, timedelta
import csv

from elasticutils.contrib.django import F, es_required_or_50x

from django.http import HttpResponse
from django.shortcuts import render
from django.utils.encoding import force_bytes
from django.views.generic.edit import FormView
from django.utils.decorators import method_decorator

from fjord.analytics.forms import OccurrencesComparisonForm, ProductsUpdateForm
from fjord.analytics.tools import (
    counts_to_options,
    zero_fill)
from fjord.base.helpers import locale_name
from fjord.base.util import (
    analyzer_required,
    check_new_user,
    smart_int,
    smart_date)
from fjord.feedback.helpers import country_name
from fjord.feedback.models import Product, Response, ResponseMappingType
from fjord.heartbeat.models import Answer as HBAnswer
from fjord.heartbeat.models import Poll as HBPoll
from fjord.search.utils import es_error_statsd


@check_new_user
@analyzer_required
def analytics_dashboard(request):
    """Main page for analytics related things"""
    template = 'analytics/analyzer/dashboard.html'
    return render(request, template)


@check_new_user
@analyzer_required
def analytics_products(request):
    """Products list view"""
    template = 'analytics/analyzer/products.html'
    products = Product.objects.all()
    return render(request, template, {
        'products': products
    })


@check_new_user
@analyzer_required
@es_required_or_50x(error_template='analytics/es_down.html')
@es_error_statsd
def analytics_occurrences(request):
    template = 'analytics/analyzer/occurrences.html'

    first_facet_bi = None
    first_params = {}
    first_facet_total = 0

    second_facet_bi = None
    second_params = {}
    second_facet_total = 0

    if 'product' in request.GET:
        form = OccurrencesComparisonForm(request.GET)
        if form.is_valid():
            cleaned = form.cleaned_data

            # First item
            first_resp_s = (ResponseMappingType.search()
                            .filter(product=cleaned['product'])
                            .filter(locale__startswith='en'))

            first_params['product'] = cleaned['product']

            if cleaned['first_version']:
                first_resp_s = first_resp_s.filter(
                    version=cleaned['first_version'])
                first_params['version'] = cleaned['first_version']
            if cleaned['first_start_date']:
                first_resp_s = first_resp_s.filter(
                    created__gte=cleaned['first_start_date'])
                first_params['date_start'] = cleaned['first_start_date']
            if cleaned['first_end_date']:
                first_resp_s = first_resp_s.filter(
                    created__lte=cleaned['first_end_date'])
                first_params['date_end'] = cleaned['first_end_date']
            if cleaned['first_search_term']:
                first_resp_s = first_resp_s.query(
                    description__match=cleaned['first_search_term'])
                first_params['q'] = cleaned['first_search_term']

            if ('date_start' not in first_params
                    and 'date_end' not in first_params):

                # FIXME - If there's no start date, then we want
                # "everything" so we use a hard-coded 2013-01-01 date
                # here to hack that.
                #
                # Better way might be to change the dashboard to allow
                # for an "infinite" range, but there's no other use
                # case for that and the ranges are done in the ui--not
                # in the backend.
                first_params['date_start'] = '2013-01-01'

            # Have to do raw because we want a size > 10.
            first_resp_s = first_resp_s.facet('description_bigrams',
                                              size=30, filtered=True)
            first_resp_s = first_resp_s[0:0]

            first_facet_total = first_resp_s.count()
            first_facet = first_resp_s.facet_counts()

            first_facet_bi = first_facet['description_bigrams']
            first_facet_bi = sorted(
                first_facet_bi, key=lambda item: -item['count'])

            if (cleaned['second_version']
                    or cleaned['second_search_term']
                    or cleaned['second_start_date']):

                second_resp_s = (ResponseMappingType.search()
                                 .filter(product=cleaned['product'])
                                 .filter(locale__startswith='en'))

                second_params['product'] = cleaned['product']

                if cleaned['second_version']:
                    second_resp_s = second_resp_s.filter(
                        version=cleaned['second_version'])
                    second_params['version'] = cleaned['second_version']
                if cleaned['second_start_date']:
                    second_resp_s = second_resp_s.filter(
                        created__gte=cleaned['second_start_date'])
                    second_params['date_start'] = cleaned['second_start_date']
                if cleaned['second_end_date']:
                    second_resp_s = second_resp_s.filter(
                        created__lte=cleaned['second_end_date'])
                    second_params['date_end'] = cleaned['second_end_date']
                if form.cleaned_data['second_search_term']:
                    second_resp_s = second_resp_s.query(
                        description__match=cleaned['second_search_term'])
                    second_params['q'] = cleaned['second_search_term']

                if ('date_start' not in second_params
                        and 'date_end' not in second_params):

                    # FIXME - If there's no start date, then we want
                    # "everything" so we use a hard-coded 2013-01-01 date
                    # here to hack that.
                    #
                    # Better way might be to change the dashboard to allow
                    # for an "infinite" range, but there's no other use
                    # case for that and the ranges are done in the ui--not
                    # in the backend.
                    second_params['date_start'] = '2013-01-01'

                # Have to do raw because we want a size > 10.
                second_resp_s = second_resp_s.facet('description_bigrams',
                                                    size=30, filtered=True)
                second_resp_s = second_resp_s[0:0]

                second_facet_total = second_resp_s.count()
                second_facet = second_resp_s.facet_counts()

                second_facet_bi = second_facet['description_bigrams']
                second_facet_bi = sorted(
                    second_facet_bi, key=lambda item: -item['count'])

        permalink = request.build_absolute_uri()

    else:
        permalink = ''
        form = OccurrencesComparisonForm()

    # FIXME - We have responses that have no product set. This ignores
    # those. That's probably the right thing to do for the Occurrences Report
    # but maybe not.
    products = [prod for prod in ResponseMappingType.get_products() if prod]

    return render(request, template, {
        'permalink': permalink,
        'form': form,
        'products': products,
        'first_facet_bi': first_facet_bi,
        'first_params': first_params,
        'first_facet_total': first_facet_total,
        'first_normalization': round(first_facet_total * 1.0 / 1000, 3),
        'second_facet_bi': second_facet_bi,
        'second_params': second_params,
        'second_facet_total': second_facet_total,
        'second_normalization': round(second_facet_total * 1.0 / 1000, 3),
        'render_time': datetime.now(),
    })


@check_new_user
@analyzer_required
@es_required_or_50x(error_template='analytics/es_down.html')
@es_error_statsd
def analytics_duplicates(request):
    """Shows all duplicate descriptions over the last n days"""
    template = 'analytics/analyzer/duplicates.html'

    n = 14

    responses = (ResponseMappingType.search()
                 .filter(created__gte=datetime.now() - timedelta(days=n))
                 .values_dict('description', 'happy', 'created', 'locale',
                              'user_agent', 'id')
                 .order_by('created').everything())

    total_count = len(responses)

    response_dupes = {}
    for resp in responses:
        response_dupes.setdefault(resp['description'], []).append(resp)

    response_dupes = [
        (key, val) for key, val in response_dupes.items()
        if len(val) > 1
    ]

    # convert the dict into a list of tuples sorted by the number of
    # responses per tuple largest number first
    response_dupes = sorted(response_dupes, key=lambda item: len(item[1]) * -1)

    # duplicate_count -> count
    # i.e. "how many responses had 2 duplicates?"
    summary_counts = defaultdict(int)
    for desc, responses in response_dupes:
        summary_counts[len(responses)] = summary_counts[len(responses)] + 1
    summary_counts = sorted(summary_counts.items(), key=lambda item: item[0])

    return render(request, template, {
        'n': 14,
        'response_dupes': response_dupes,
        'render_time': datetime.now(),
        'summary_counts': summary_counts,
        'total_count': total_count,
    })


def _analytics_search_export(request, opinions_s):
    """Handles CSV export for analytics search

    This only exports MAX_OPINIONS amount. It adds a note to the top
    about that if the results are truncated.

    """
    MAX_OPINIONS = 1000

    # Create the HttpResponse object with the appropriate CSV header.
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="{0}"'.format(
        datetime.now().strftime('%Y%m%d_%H%M_search_export.csv'))

    keys = Response.get_export_keys(confidential=True)
    total_opinions = opinions_s.count()

    opinions_s = opinions_s.values_list('id')[:MAX_OPINIONS]

    # We convert what we get back from ES to what's in the db so we
    # can get all the information.
    opinions = Response.objects.filter(id__in=[mem[0] for mem in opinions_s])

    writer = csv.writer(response)

    # Specify what this search is
    writer.writerow(['URL: {0}'.format(request.get_full_path())])
    writer.writerow(['Params: ' +
                     ' '.join(['{0}: {1}'.format(key, val)
                               for key, val in request.GET.items()])])

    # Add note if we truncated.
    if total_opinions > MAX_OPINIONS:
        writer.writerow(['Truncated {0} rows.'.format(
            total_opinions - MAX_OPINIONS)])

    # Write headers row.
    writer.writerow(keys)

    # Write opinion rows.
    for op in opinions:
        writer.writerow([force_bytes(getattr(op, key)) for key in keys])

    return response


@check_new_user
@analyzer_required
@es_required_or_50x(error_template='analytics/es_down.html')
@es_error_statsd
def analytics_search(request):
    template = 'analytics/analyzer/search.html'

    output_format = request.GET.get('format', None)
    page = smart_int(request.GET.get('page', 1), 1)

    # Note: If we add additional querystring fields, we need to add
    # them to generate_dashboard_url.
    search_happy = request.GET.get('happy', None)
    search_has_email = request.GET.get('has_email', None)
    search_platform = request.GET.get('platform', None)
    search_locale = request.GET.get('locale', None)
    search_country = request.GET.get('country', None)
    search_product = request.GET.get('product', None)
    search_domain = request.GET.get('domain', None)
    search_api = smart_int(request.GET.get('api', None), fallback=None)
    search_version = request.GET.get('version', None)
    search_query = request.GET.get('q', None)
    search_date_start = smart_date(
        request.GET.get('date_start', None), fallback=None)
    search_date_end = smart_date(
        request.GET.get('date_end', None), fallback=None)
    search_bigram = request.GET.get('bigram', None)
    search_source = request.GET.get('source', None)
    search_campaign = request.GET.get('campaign', None)
    search_organic = request.GET.get('organic', None)
    selected = request.GET.get('selected', None)

    filter_data = []
    current_search = {'page': page}

    search = ResponseMappingType.search()
    f = F()
    # If search happy is '0' or '1', set it to False or True, respectively.
    search_happy = {'0': False, '1': True}.get(search_happy, None)
    if search_happy in [False, True]:
        f &= F(happy=search_happy)
        current_search['happy'] = int(search_happy)

    # If search has_email is '0' or '1', set it to False or True,
    # respectively.
    search_has_email = {'0': False, '1': True}.get(search_has_email, None)
    if search_has_email in [False, True]:
        f &= F(has_email=search_has_email)
        current_search['has_email'] = int(search_has_email)

    def unknown_to_empty(text):
        """Convert "Unknown" to "" to support old links"""
        return u'' if text.lower() == u'unknown' else text

    if search_platform is not None:
        f &= F(platform=unknown_to_empty(search_platform))
        current_search['platform'] = search_platform
    if search_locale is not None:
        f &= F(locale=unknown_to_empty(search_locale))
        current_search['locale'] = search_locale
    if search_product is not None:
        f &= F(product=unknown_to_empty(search_product))
        current_search['product'] = search_product

        # Only show the version if there's a product.
        if search_version is not None:
            # Note: We only filter on version if we're filtering on
            # product.
            f &= F(version=unknown_to_empty(search_version))
            current_search['version'] = search_version

        # Only show the country if the product is Firefox OS.
        if search_country is not None and search_product == 'Firefox OS':
            f &= F(country=unknown_to_empty(search_country))
            current_search['country'] = search_country
    if search_domain is not None:
        f &= F(url_domain=unknown_to_empty(search_domain))
        current_search['domain'] = search_domain
    if search_api is not None:
        f &= F(api=search_api)
        current_search['api'] = search_api

    if search_date_start is None and search_date_end is None:
        selected = '7d'

    if search_date_end is None:
        search_date_end = datetime.now()
    if search_date_start is None:
        search_date_start = search_date_end - timedelta(days=7)

    current_search['date_end'] = search_date_end.strftime('%Y-%m-%d')
    # Add one day, so that the search range includes the entire day.
    end = search_date_end + timedelta(days=1)
    # Note 'less than', not 'less than or equal', because of the added
    # day above.
    f &= F(created__lt=end)

    current_search['date_start'] = search_date_start.strftime('%Y-%m-%d')
    f &= F(created__gte=search_date_start)

    if search_query:
        current_search['q'] = search_query
        search = search.query(description__sqs=search_query)

    if search_bigram is not None:
        f &= F(description_bigrams=search_bigram)
        filter_data.append({
            'display': 'Bigram',
            'name': 'bigram',
            'options': [{
                'count': 'all',
                'name': search_bigram,
                'display': search_bigram,
                'value': search_bigram,
                'checked': True
            }]
        })

    if search_source is not None:
        f &= F(source=search_source)
        current_search['source'] = search_source
    if search_campaign is not None:
        f &= F(campaign=search_campaign)
        current_search['campaign'] = search_campaign
    search_organic = {'0': False, '1': True}.get(search_organic, None)
    if search_organic in [False, True]:
        f &= F(organic=search_organic)
        current_search['organic'] = int(search_organic)

    search = search.filter(f).order_by('-created')

    # If they're asking for a CSV export, then send them to the export
    # screen.
    if output_format == 'csv':
        return _analytics_search_export(request, search)

    # Search results and pagination
    if page < 1:
        page = 1
    page_count = 50
    start = page_count * (page - 1)
    end = start + page_count

    search_count = search.count()
    opinion_page_ids = [mem[0] for mem in search.values_list('id')[start:end]]

    # We convert what we get back from ES to what's in the db so we
    # can get all the information.
    opinion_page = Response.objects.filter(id__in=opinion_page_ids)

    # Navigation facet data

    # This loop does two things. First it maps 'T' -> True and 'F' ->
    # False.  This is probably something EU should be doing for
    # us. Second, it restructures the data into a more convenient
    # form.
    counts = {
        'happy': {},
        'has_email': {},
        'platform': {},
        'locale': {},
        'country': {},
        'product': {},
        'version': {},
        'url_domain': {},
        'api': {},
        'source': {},
        'campaign': {},
        'organic': {},
    }
    facets = search.facet(*(counts.keys()),
                          filtered=bool(search._process_filters(f.filters)),
                          size=25)

    for param, terms in facets.facet_counts().items():
        for term in terms:
            name = term['term']
            if name == 'T':
                name = True
            elif name == 'F':
                name = False

            counts[param][name] = term['count']

    def empty_to_unknown(text):
        return 'Unknown' if text == u'' else text

    filter_data.extend([
        counts_to_options(
            counts['happy'].items(),
            name='happy',
            display='Sentiment',
            display_map={True: 'Happy', False: 'Sad'},
            value_map={True: 1, False: 0},
            checked=search_happy),
        counts_to_options(
            counts['has_email'].items(),
            name='has_email',
            display='Has email',
            display_map={True: 'Yes', False: 'No'},
            value_map={True: 1, False: 0},
            checked=search_has_email),
        counts_to_options(
            counts['product'].items(),
            name='product',
            display='Product',
            display_map=empty_to_unknown,
            checked=search_product)
    ])
    # Only show the version if we're showing a specific
    # product.
    if search_product:
        filter_data.append(
            counts_to_options(
                counts['version'].items(),
                name='version',
                display='Version',
                display_map=empty_to_unknown,
                checked=search_version)
        )
        # Only show the country if the product is Firefox OS.
        if search_product == 'Firefox OS':
            filter_data.append(
                counts_to_options(
                    counts['country'].items(),
                    name='country',
                    display='Country',
                    checked=search_country,
                    display_map=country_name),
            )

    filter_data.extend(
        [
            counts_to_options(
                counts['platform'].items(),
                name='platform',
                display='Platform',
                display_map=empty_to_unknown,
                checked=search_platform),
            counts_to_options(
                counts['locale'].items(),
                name='locale',
                display='Locale',
                checked=search_locale,
                display_map=locale_name),
            counts_to_options(
                counts['url_domain'].items(),
                name='domain',
                display='Domain',
                checked=search_domain,
                display_map=empty_to_unknown),
            counts_to_options(
                counts['api'].items(),
                name='api',
                display='API version',
                checked=search_api,
                display_map=empty_to_unknown),
            counts_to_options(
                counts['organic'].items(),
                name='organic',
                display='Organic',
                display_map={True: 'Yes', False: 'No'},
                value_map={True: 1, False: 0},
                checked=search_organic),
            counts_to_options(
                counts['source'].items(),
                name='source',
                display='Source',
                checked=search_source,
                display_map=empty_to_unknown),
            counts_to_options(
                counts['campaign'].items(),
                name='campaign',
                display='Campaign',
                checked=search_campaign,
                display_map=empty_to_unknown),
        ]
    )

    return render(request, template, {
        'opinions': opinion_page,
        'opinion_count': search_count,
        'filter_data': filter_data,
        'page': page,
        'prev_page': page - 1 if start > 0 else None,
        'next_page': page + 1 if end < search_count else None,
        'current_search': current_search,
        'selected': selected,
    })


@check_new_user
@analyzer_required
def analytics_hb(request):
    """Shows HB data"""
    template = 'analytics/analyzer/hb.html'
    hb_polls = HBPoll.objects.filter(enabled=True)
    hb_data = HBAnswer.objects.order_by('-created')[:100]

    return render(request, template, {
        'hb_polls': hb_polls,
        'hb_data': hb_data
    })


@check_new_user
@analyzer_required
@es_required_or_50x(error_template='analytics/es_down.html')
@es_error_statsd
def analytics_hourly_histogram(request):
    """Shows an hourly histogram for the last 5 days of all responses"""
    template = 'analytics/analyzer/hourly_histogram.html'

    date_end = smart_date(
        request.GET.get('date_end', None), fallback=None)

    if date_end is None:
        date_end = date.today()

    date_start = date_end - timedelta(days=5)

    search = ResponseMappingType.search()
    filters = F(created__gte=date_start, created__lte=date_end)
    search.filter(filters)

    hourly_histogram = search.facet_raw(
        hourly={
            'date_histogram': {'interval': 'hour', 'field': 'created'},
            'facet_filter': search._process_filters(filters.filters)
        }).facet_counts()

    hourly_data = dict((p['time'], p['count'])
                       for p in hourly_histogram['hourly'])

    hour = 60 * 60 * 1000.0
    zero_fill(date_start, date_end, [hourly_data], spacing=hour)

    # FIXME: This is goofy. After zero_fill, we end up with a bunch of
    # trailing zeros for reasons I don't really understand, so instead
    # of fixing that, I'm just going to remove them here.
    hourly_data = sorted(hourly_data.items())
    while hourly_data and hourly_data[-1][1] == 0:
        hourly_data.pop(-1)

    histogram = [
        {'label': 'Hourly', 'name': 'hourly',
         'data': hourly_data},
    ]

    return render(request, template, {
        'histogram': histogram,
        'start_date': date_start,
        'end_date': date_end
    })


class ProductsUpdateView(FormView):
    """An administrator view for showing, adding, and updating the products."""
    template_name = 'analytics/analyzer/addproducts.html'
    form_class = ProductsUpdateForm
    success_url = 'products'

    @method_decorator(check_new_user)
    @method_decorator(analyzer_required)
    def dispatch(self, *args, **kwargs):
        return super(ProductsUpdateView, self).dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super(ProductsUpdateView, self).get_context_data(**kwargs)
        context['products'] = Product.uncached.all()
        return context

    def form_valid(self, form):
        try:
            instance = Product.objects.get(db_name=form.data.get('db_name'))
            instance.slug = form.data.get('slug') or instance.slug
            instance.display_name = (form.data.get('display_name') or
                                     instance.display_name)
            instance.notes = form.data.get('notes') or instance.notes
            instance.enabled = form.data.get('enabled') or False
            instance.on_dashboard = form.data.get('on_dashboard') or False
            instance.save()
        except Product.DoesNotExist:
            form.save()
        return super(ProductsUpdateView, self).form_valid(form)
