#!/usr/bin/env ruby
# Memory-only tests: no router access and no configuration writes.
require_relative 'personal-rules'

def check(condition, message)
  raise message unless condition
end

check(Mudi7PersonalRules.rules_nodes('') == [nil, nil], 'Psych empty-document false return was not handled')
check(Mudi7PersonalRules.rules_nodes("# comment only\n") == [nil, nil], 'Psych comment-only document was not handled')

template = <<~YAML
  # 保留原有模板说明
  rule-providers:
    existing:
      type: file
      path: ./existing.yaml
  rules:
  ##- DOMAIN-SUFFIX,example.com,PROXY # 模板示例
  - DOMAIN-SUFFIX,example.org,PROXY
  other-setting: keep
YAML
merged = Mudi7PersonalRules.merge(template)
check(merged.include?('# 保留原有模板说明'), 'Template comment was lost')
check(merged.include?('##- DOMAIN-SUFFIX,example.com,PROXY # 模板示例'), 'Example comment was lost')
check(merged.include?("    path: ./existing.yaml\n"), 'Provider data was changed')
check(merged.include?("other-setting: keep\n"), 'Other data was changed')
check(YAML.safe_load(merged)['rules'].first == Mudi7PersonalRules::RULE, 'Rule was not first')
check(Mudi7PersonalRules.merge(merged) == merged, 'Second merge changed the content')

duplicates = <<~YAML
  rules:
    - DOMAIN-SUFFIX,example.org,PROXY
    - "DOMAIN-SUFFIX,example.com,DIRECT" # 保留备注一
    - 'DOMAIN-SUFFIX, EXAMPLE.COM, DIRECT' # 保留备注二
    - DOMAIN-SUFFIX,example.com,PROXY
  metadata: unchanged
YAML
deduplicated = Mudi7PersonalRules.merge(duplicates)
items = YAML.safe_load(deduplicated)['rules']
check(items.first == Mudi7PersonalRules::RULE, 'Duplicate merge did not put direct rule first')
check(items.count { |rule| rule.split(',').map(&:strip).map(&:downcase) == %w[domain-suffix example.com direct] } == 1, 'Direct rule was duplicated')
check(items.include?('DOMAIN-SUFFIX,example.com,PROXY'), 'A different policy was removed')
check(deduplicated.include?('# 保留备注一') && deduplicated.include?('# 保留备注二'), 'Trailing comments were lost')
check(Mudi7PersonalRules.merge(deduplicated) == deduplicated, 'Deduplication was not idempotent')

correct_first = "rules:\n  - 'DOMAIN-SUFFIX, example.com, DIRECT' # existing\n  - MATCH,PROXY\n"
check(Mudi7PersonalRules.merge(correct_first) == correct_first, 'An already correct first rule was rewritten')
first_duplicate = correct_first + "  - DOMAIN-SUFFIX,example.com,DIRECT # duplicate\n"
first_dedup = Mudi7PersonalRules.merge(first_duplicate)
check(first_dedup.include?("  - 'DOMAIN-SUFFIX, example.com, DIRECT' # existing\n"), 'First rule formatting was changed')
check(first_dedup.include?('# duplicate'), 'Duplicate rule comment was lost')
check(Mudi7PersonalRules.merge(first_dedup) == first_dedup, 'First-rule deduplication was not idempotent')

['', "# comment only\n", "rule-providers: {}\n", 'rules:', "rules: null # keep\n", "rules: [] # keep\n"].each do |input|
  output = Mudi7PersonalRules.merge(input)
  check(YAML.safe_load(output)['rules'] == [Mudi7PersonalRules::RULE], 'Empty or missing rules were not handled')
  check(Mudi7PersonalRules.merge(output) == output, 'Empty-input merge was not idempotent')
end
crlf = "rules:\r\n  # keep\r\n  - MATCH,PROXY\r\n"
crlf_output = Mudi7PersonalRules.merge(crlf)
check(!crlf_output.gsub("\r\n", '').include?("\n"), 'CRLF line endings were changed')

_, suffix, policy = Mudi7PersonalRules::RULE.split(',')
matches_suffix = ->(host) { host.downcase == suffix || host.downcase.end_with?('.' + suffix) }
check(policy == 'DIRECT', 'Target policy is not DIRECT')
%w[example.com www.example.com a.b.example.com WWW.EXAMPLE.COM].each do |host|
  check(matches_suffix.call(host), 'Root or child domain did not match: ' + host)
end
%w[other-example.com example.com.example.com unrelated.top].each do |host|
  check(!matches_suffix.call(host), 'Unrelated domain matched: ' + host)
end

begin
  Mudi7PersonalRules.merge("rules: [MATCH,PROXY]\n")
  raise 'Unsupported inline rules did not fail safely'
rescue ArgumentError
  # Expected; the caller never writes a result when parsing/validation fails.
end

puts 'PASS: comments, providers, ordering, suffix scope, deduplication, idempotence, empty lists, CRLF, safe rejection'
