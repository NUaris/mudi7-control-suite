local m=assert(loadfile('/etc/mudi7-management/radio-scan.lua'))()
if arg[1]=='worker' then m.run('cellular')
elseif arg[1]=='scan' then print(require'cjson'.encode(m.start('cellular')))
elseif arg[1]=='status' then print(require'cjson'.encode(m.status('cellular')))
else io.stderr:write('Usage: lua mudi7-cellular-scan.lua scan|status\n');os.exit(2) end
