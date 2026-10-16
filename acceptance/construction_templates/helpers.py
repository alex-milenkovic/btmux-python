import io
from data import templates as t
from . import step,eq,text,unit


@step(r'a bit table with Alpha Beta and Gamma in that order')
def table(w):w['table']=('Alpha','Beta','Gamma')


@step(r'the (strict|lenient|delimited) bit parser reads (.+)')
def parse(w,parser,value):
    fn={'strict':t.parse_bit_vector,'lenient':t.parse_bit_vector_lenient,'delimited':t.parse_bit_vector_delim}[parser]
    w['result']=fn(w['table'],text(value))


@step(r'its integer result is (-?\d+)')
def parsed(w,value):eq(w['result'],int(value))


@step(r'read_desc reads same-line data (.+) with an empty remaining stream')
def desc(w,value):w['result']=t.read_brace_block(io.StringIO(''),text(value))


@step(r'the returned bytes are (.+)')
def bytes_result(w,value):eq(w['result'],text(value))


@step(r'a unit with computer0 radio3 scan (\d+) tac9 lrs9 and radio range9')
def computer(w,scan):
    u=w['unit'];u.computer=0;u.radio=3;u.scan_range=int(scan);u.tac_range=u.lrs_range=u.radio_range=9


@step(r'legacy computer conversion runs')
def convert(w):t.computer_conversion(w['unit'])


@step(r'computer scan tac lrs and radio range are (\d+) (\d+) (\d+) (\d+) and (\d+)')
def converted(w,*values):
    u=w['unit'];eq((u.computer,u.scan_range,u.tac_range,u.lrs_range,u.radio_range),tuple(map(int,values)))


@step(r'unit type (.+)')
def kind(w,value):unit(w,value)


@step(r'default fuel is requested')
def fuel(w):w['result']=t.default_fuel_by_type(w['unit'])


@step(r'fuel is (\d+)')
def fueled(w,value):eq(w['result'],int(value))
