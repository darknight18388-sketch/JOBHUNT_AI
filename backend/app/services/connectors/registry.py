from app.services.connectors.adzuna import AdzunaConnector
from app.services.connectors.arbeitnow import ArbeitnowConnector
from app.services.connectors.base import JobConnector
from app.services.connectors.jooble import JoobleConnector
from app.services.connectors.remotive import RemotiveConnector
from app.services.connectors.rss import RssConnector

CONNECTORS: dict[str, JobConnector] = {
    c.key: c for c in (RemotiveConnector(), RssConnector(), AdzunaConnector(),
                       JoobleConnector(), ArbeitnowConnector())
}
