from datetime import datetime


DEFAULT_PLAN_TIER = 'free'


PLAN_RULES = {
    'free': {
        'label': 'Free',
        'max_active_jobs': 1,
        'monthly_job_posts': 1,
        'can_view_top_candidates': False,
        'can_use_messages': False,
    },
    'starter': {
        'label': 'Starter',
        'max_active_jobs': 10,
        'monthly_job_posts': 30,
        'can_view_top_candidates': True,
        'can_use_messages': True,
    },
    'pro': {
        'label': 'Pro',
        'max_active_jobs': 50,
        'monthly_job_posts': 200,
        'can_view_top_candidates': True,
        'can_use_messages': True,
    },
    'enterprise': {
        'label': 'Enterprise',
        'max_active_jobs': None,
        'monthly_job_posts': None,
        'can_view_top_candidates': True,
        'can_use_messages': True,
    },
}


def normalize_plan_tier(value, default=DEFAULT_PLAN_TIER):
    cleaned = (value or '').strip().lower()
    if cleaned in PLAN_RULES:
        return cleaned
    return default


def get_plan_rules(value):
    return PLAN_RULES[normalize_plan_tier(value)]


def plan_label(value):
    return get_plan_rules(value)['label']


def can_access_feature(plan_tier, feature_key):
    rules = get_plan_rules(plan_tier)
    return bool(rules.get(feature_key))


def can_create_job(plan_tier, active_jobs_count, posted_this_month_count):
    rules = get_plan_rules(plan_tier)

    active_limit = rules.get('max_active_jobs')
    if active_limit is not None and active_jobs_count >= active_limit:
        return False, f'Your {rules["label"]} plan allows up to {active_limit} active job posts.'

    monthly_limit = rules.get('monthly_job_posts')
    if monthly_limit is not None and posted_this_month_count >= monthly_limit:
        month_name = datetime.utcnow().strftime('%B')
        return False, f'Your {rules["label"]} plan monthly posting limit ({monthly_limit}) is reached for {month_name}.'

    return True, ''
