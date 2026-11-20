"""M6 iteration monitor (10 ES persons only; never calibration persons). python3 -m model.hg2.iter_check"""
import json
from .train import norm
from .eval import members, es_monitor
print(json.dumps(es_monitor(members(), norm()), indent=1))
