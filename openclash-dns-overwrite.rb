require 'yaml'
path = ARGV.fetch(0)
value = YAML.load_file(path, aliases: true)
dns = value['dns'] ||= {}
operation = dns['enhanced-mode']
proxy_mode = value['mode'].to_s.downcase
if operation == 'redir-host' && proxy_mode != 'direct'
  group = (value['proxy-groups'] || []).first&.fetch('name', nil)
  # Real AAAA records must not come from censored DNS (e.g. bogus 2001::1).
  dns['nameserver'] = ['https://1.1.1.1/dns-query#' + group] if group
end
# Never bootstrap through system DNS, which now points back to AdGuard Home.
dns['default-nameserver'] = ['223.5.5.5', '119.29.29.29']
dns['proxy-server-nameserver'] = ['https://223.5.5.5/dns-query', 'https://doh.pub/dns-query']
if dns['nameserver-policy']
  dns['proxy-server-nameserver-policy'] = dns['nameserver-policy'].transform_values { |x| x.is_a?(Array) ? x.dup : x }
end
# Keep DNS endpoints and proxy server names real, including nested client proxies.
real_hosts = (value['proxies'] || []).map { |p| p['server'] }
resolver_urls = %w[nameserver fallback proxy-server-nameserver].flat_map { |k| dns[k] || [] }
resolver_urls += (dns['nameserver-policy'] || {}).values.flatten
resolver_urls.each do |url|
  host = url.to_s[/\A[a-z]+:\/\/([^\/:#]+)/, 1]
  real_hosts << host if host
end
dns['fake-ip-filter'] = ((dns['fake-ip-filter'] || []) + real_hosts.compact.select { |x| x.match?(/[a-z]/i) }).uniq
dns['fake-ip-range6'] = 'fdfe:dcba:9876::1/64' if dns['enhanced-mode'] == 'fake-ip'
File.write(path, YAML.dump(value))
