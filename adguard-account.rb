require 'yaml'
input = YAML.safe_load(STDIN.read)
init = '/etc/init.d/adguardhome'
text = File.read(init)
raise 'native GL flag missing' unless text.include?('AdGuardHome --glinet ')
path = '/etc/AdGuardHome/config.yaml'
value = YAML.load_file(path, aliases: true)
users = value['users'] ||= []
raise 'unexpected service account collision' if users.any? { |u| u['name'] == input.fetch('service_name') }
users.reject! { |u| u['name'] == input.fetch('name') }
users << {'name' => input.fetch('name'), 'password' => input.fetch('password_hash')}
users << {'name' => input.fetch('service_name'), 'password' => input.fetch('service_hash')}
File.write(path + '.new', YAML.dump(value))
File.chmod(0600, path + '.new')
File.rename(path + '.new', path)
auth = '/etc/mudi7-management/adguard-api.authorization'
File.write(auth + '.new', input.fetch('authorization') + "\n")
File.chmod(0600, auth + '.new')
File.rename(auth + '.new', auth)
File.write(init + '.new', text.sub('AdGuardHome --glinet ', 'AdGuardHome '))
File.chmod(0755, init + '.new')
File.rename(init + '.new', init)
puts 'local accounts configured; passwords are bcrypt hashes'
