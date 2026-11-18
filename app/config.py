from pathlib import Path
TITLE = '粮仓水分折标与干物质守恒'
SHORT = 'grain-dry'
STAGES = ['intake', 'contract', 'dryweight', 'truckmerge', 'balance', 'settlement', 'trace']
MODULES = ['磅单接收', '水杂契约', '折标计算', '车次归并', '仓批平衡', '结算复核', '批次追溯']
COLUMNS = {'id': '磅单号', 'bin': '仓号', 'net_kg': '净重 kg', 'dry_kg': '干物质 kg', 'standard_kg': '折标 kg', 'amount': '结算 CNY', 'count': '车次', 'line': '行号', 'code': '原因码', 'reason': '原因', 'version': '版本', 'fingerprint': '摘要'}
DEFAULTS = {'standard_moisture': '14', 'max_moisture': '28', 'price': '2.6', 'bin_tolerance': '0.01'}
RULE_VERSION = "2026.11.18-v1"
SAMPLES = Path(__file__).resolve().parent.parent / "sample_data"
MAX_BYTES = 4 * 1024 * 1024

COLUMNS.update({'clean_kg':'净粮 kg','delta_kg':'平衡差 kg','moisture':'水分 %','impurity':'杂质 %','key':'业务键','detail':'依据','unit':'单位','gross':'毛重','tare':'皮重'})
COLUMNS.update({'trip_id':'车次','plate':'车牌','day':'日期','gross_event_id':'毛重磅单','tare_event_id':'皮重磅单',
                'weighed_local':'称重时间','weight_kg':'重量 kg','tare_state':'皮重状态','estimate_source':'暂估来源',
                'estimated_amount':'暂估 CNY','confirmed_amount':'已定 CNY','pending':'待皮重','confirmed':'已定',
                'trips':'车次','upload_id':'上传批次','created':'时间','rows':'行数','accepted':'采信',
                'quarantined':'隔离','note':'备注','event_id':'称重号','state':'状态','upload':'上传'})
