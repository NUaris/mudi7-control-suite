require 'yaml'
path = '/etc/AdGuardHome/config.yaml'
value = YAML.load_file(path)
dns = value['dns'] ||= {}
dns['bind_hosts'] = ['127.0.0.1']
dns['port'] = 3053
dns['upstream_dns'] = ['223.5.5.5', '119.29.29.29']
dns['fallback_dns'] = ['223.6.6.6', '119.29.29.29']
dns['bootstrap_dns'] = ['223.5.5.5', '119.29.29.29']
dns['cache_size'] = 0
dns['cache_min_ttl'] = 0
dns['cache_optimistic'] = false
dns['use_private_ptr_resolvers'] = false
dns['local_ptr_upstreams'] = []
dns['protection_enabled'] = true
dns['aaaa_disabled'] = false
dns['upstream_timeout'] = '3s'
value['language'] = 'zh-cn'
File.write(path + '.new', YAML.dump(value))
File.chmod(0600, path + '.new')
File.rename(path + '.new', path)
