#!/usr/bin/env ruby
# Merge only the supplied OpenClash custom-rules file; do not touch subscriptions.
require 'yaml'

module Mudi7PersonalRules
  RULE = 'DOMAIN-SUFFIX,example.com,DIRECT'.freeze

  def self.task_rule?(node)
    return false unless node.is_a?(Psych::Nodes::Scalar)
    parts = node.value.split(',').map(&:strip)
    parts.length == 3 && parts[0].upcase == 'DOMAIN-SUFFIX' &&
      parts[1].downcase == 'example.com' && parts[2].upcase == 'DIRECT'
  end

  def self.rules_nodes(content)
    document = Psych.parse(content)
    root = document && document.root
    return [nil, nil] unless root
    raise ArgumentError, 'Custom rules must have a YAML mapping at the top level' unless root.is_a?(Psych::Nodes::Mapping)
    pairs = root.children.each_slice(2).select { |key, _| key.is_a?(Psych::Nodes::Scalar) && key.value == 'rules' }
    raise ArgumentError, 'Multiple rules keys are ambiguous; no file was changed' if pairs.length > 1
    pairs.first || [nil, nil]
  end

  def self.merge(content)
    key, value = rules_nodes(content)
    newline = content.include?("\r\n") ? "\r\n" : "\n"
    unless key
      prefix = content.empty? || content.end_with?("\n") ? content : content + newline
      output = prefix + "rules:#{newline}  - #{RULE}#{newline}"
      _, added_value = rules_nodes(output)
      unless added_value.is_a?(Psych::Nodes::Sequence) && task_rule?(added_value.children.first)
        raise ArgumentError, 'Added rules failed validation; no file was changed'
      end
      return output
    end

    sequence = value.is_a?(Psych::Nodes::Sequence)
    empty_scalar = value.is_a?(Psych::Nodes::Scalar) && value.plain && ['', '~', 'null', 'Null', 'NULL'].include?(value.value)
    unless sequence || empty_scalar
      raise ArgumentError, 'rules must be a YAML list or empty; no file was changed'
    end
    if sequence && value.style == Psych::Nodes::Sequence::FLOW && !value.children.empty?
      raise ArgumentError, 'Non-empty inline rules lists are unsupported; use a block list before merging'
    end
    children = sequence ? value.children : []
    unless children.all? { |node| node.is_a?(Psych::Nodes::Scalar) }
      raise ArgumentError, 'Every rules item must be a string; no file was changed'
    end

    matches = children.select { |node| task_rule?(node) }
    already_first = !children.empty? && task_rule?(children.first)
    return content if already_first && matches.length == 1

    lines = content.lines
    indentation = if children.empty?
                    '  '
                  else
                    lines[children.first.start_line][/\A([ ]*)-/, 1] || raise(ArgumentError, 'Cannot locate the block rules list')
                  end

    # Keep a correct first item verbatim (including its quotes and comment).
    # Remove only extra task rules, retaining their trailing YAML comments.
    removals = already_first ? matches.drop(1) : matches
    removals.reverse_each do |node|
      last_line = node.end_line
      last_line -= 1 if node.end_column.zero? && last_line > node.start_line
      span = lines[node.start_line..last_line]
      comments = span.select { |line| line.match?(/\A[ ]*#/) }
      if last_line == node.end_line
        suffix = lines[last_line][node.end_column..-1].to_s
        if suffix.match?(/\A[ \t]*#/)
          comments << indentation + suffix.lstrip
          comments[-1] += newline unless comments[-1].end_with?("\n")
        end
      end
      lines[node.start_line..last_line] = comments
    end

    unless already_first
      # Empty/null/[] may occupy the rules line; remove only that scalar token.
      if !sequence || value.children.empty?
        if value.start_line != value.end_line
          raise ArgumentError, 'Multiline empty rules values are unsupported; no file was changed'
        end
        lines[value.start_line][value.start_column...value.end_column] = ''
      end
      lines[key.end_line] += newline unless lines[key.end_line].end_with?("\n")
      lines.insert(key.end_line + 1, indentation + "- #{RULE}" + newline)
    end

    output = lines.join
    _, merged_value = rules_nodes(output)
    unless merged_value.is_a?(Psych::Nodes::Sequence) && task_rule?(merged_value.children.first) &&
           merged_value.children.count { |node| task_rule?(node) } == 1
      raise ArgumentError, 'Merged rules failed validation; no file was changed'
    end
    output
  end

  def self.apply(path)
    raise ArgumentError, 'Specify one existing OpenClash custom-rules file' unless File.file?(path)
    content = File.binread(path).force_encoding(Encoding::UTF_8)
    output = merge(content)
    return false if output == content
    File.binwrite(path, output)
    true
  end
end

if $PROGRAM_NAME == __FILE__
  begin
    raise ArgumentError, 'Usage: personal-rules.rb /etc/openclash/custom/openclash_custom_rules.list' unless ARGV.length == 1
    puts(Mudi7PersonalRules.apply(ARGV.fetch(0)) ? 'Personal direct rule merged' : 'Personal direct rule already current')
  rescue StandardError => error
    warn error.message
    exit 1
  end
end
