"""Ordered local source channels and object hooks.

Channel subscribers receive raw source text. Hook handlers implement local
object actions; absent handlers remain explicit, unapplied attempts. Neither
adapter evaluates MUX attributes; remote transport is an explicitly configured callback.
"""


class LocalEffects:
    def __init__(self):
        self.channels = []
        self.subscribers = {}
        self.hooks = {}
        self.hook_calls = []
        self.logs = []
        self.notifications = []
        self.notification_clients = {}
        self.notification_listeners = {}
        self.notification_forwards = {}

    def connect_client(self, actor, send, render=None):
        """Bind a client callback and optional raw-source-text renderer."""
        self.notification_clients[id(actor)] = (send, render)
        actor.effects = self

    def listen(self, actor, callback):
        """Callbacks receive (actor, raw text, sender, source flags)."""
        self.notification_listeners.setdefault(id(actor), []).append(callback)
        actor.effects = self

    def forward(self, actor, recipient):
        self.notification_forwards.setdefault(id(actor), []).append(recipient)
        actor.effects = self
        recipient.effects = self

    def notify(self, actor, request, path):
        from systems.notifications import personal_notify, MSG_COLORIZE
        self.notifications.append(request)
        key = id(actor)
        text, sender, flags = request['message'], request['sender'], request['flags']
        client = self.notification_clients.get(key)
        if client is not None:
            send, render = client
            send(render(text) if render is not None and flags & MSG_COLORIZE else text)
            request['client_applied'] = True
        if not getattr(actor, 'halted', False):
            for callback in tuple(self.notification_listeners.get(key, ())):
                callback(actor, text, sender, flags)
        request['forwarded'] = []
        for recipient in tuple(self.notification_forwards.get(key, ())):
            if personal_notify(recipient, text, sender=sender, flags=flags, _path=path):
                request['forwarded'].append(getattr(recipient, '_id', -1))

    def log(self, category, primary, secondary, text):
        self.logs.append(dict(category=category, primary=primary, secondary=secondary, text=text))

    def subscribe(self, channel, actor):
        self.subscribers.setdefault(channel, []).append(actor)

    def publish(self, channel, text):
        from systems.notifications import personal_notify
        recipients = []
        for actor in tuple(self.subscribers.get(channel, ())):
            personal_notify(actor, text)
            recipients.append(getattr(actor, '_id', None))
        self.channels.append(dict(channel=channel, text=text, recipients=recipients))
        return recipients

    def invoke(self, operation, actor, victim, args):
        handler = self.hooks.get((victim._id, operation))
        request = dict(operation=operation, actor=actor._id, victim=victim._id,
                       args=list(args), applied=False)
        self.hook_calls.append(request)
        if handler is not None:
            handler(actor, victim, *args)
            request['applied'] = True
        return request['applied']


def effect_sink(owner):
    return (getattr(owner, 'effects', None)
            or getattr(getattr(owner, '_engine', None), 'effects', None)
            or getattr(getattr(owner, '_character_store', None), 'effects', None))


def emit_channel(owner, channel, text, *, label=None):
    request = dict(channel=label or channel, source_channel=channel, text=text, applied=False)
    owner.channel_requests = getattr(owner, 'channel_requests', [])
    owner.channel_requests.append(request)
    sink = effect_sink(owner)
    if sink is not None:
        request['recipients'] = sink.publish(channel, text)
        request['applied'] = True
    return request


def diagnostic(owner, text, destination='stderr'):
    record=dict(destination=destination,text=text)
    owner.diagnostics=getattr(owner,'diagnostics',[])
    owner.diagnostics.append(record)
    engine=getattr(owner,'_engine',None)
    if engine is not None:
        engine.diagnostics=getattr(engine,'diagnostics',[])
        engine.diagnostics.append(record)
    return record


def send_error(owner, text):
    return emit_channel(owner, 'MechErrors', text)


def send_debug(owner, text):
    owner.debug_messages = getattr(owner, 'debug_messages', [])
    owner.debug_messages.append(text)
    return emit_channel(owner, 'MechDebugInfo', text)


def emit_log(owner, category, primary, secondary, text):
    request=dict(category=category,primary=primary,secondary=secondary,text=text,applied=False)
    owner.log_requests=getattr(owner,'log_requests',[])
    owner.log_requests.append(request)
    sink=effect_sink(owner)
    if sink is not None:
        sink.log(category,primary,secondary,text)
        request['applied']=True
    return request


def invoke_hook(owner, operation, actor, victim, args):
    request = dict(operation=operation, actor=actor._id, victim=victim._id,
                   args=list(args), applied=False)
    owner.hook_requests = getattr(owner, 'hook_requests', [])
    owner.hook_requests.append(request)
    sink = effect_sink(owner)
    if sink is not None:
        request['applied'] = sink.invoke(operation, actor, victim, args)
    return request


def did_it(owner, actor, victim, what=None, default=None, owhat=None, odefault=None, awhat=None, args=()):
    """Source did_it fields with literal local attributes and configured actions.

    Attribute expression evaluation remains the configured hook's responsibility;
    arbitrary server command strings are never treated as Python commands.
    """
    from core.attributes import attributes_for
    from systems.notifications import personal_notify
    from types import SimpleNamespace
    world=getattr(owner,'personnel',None) or getattr(getattr(owner,'_engine',None),'personnel',None)
    engine=owner if hasattr(owner,'get_entities') else getattr(owner,'_engine',None)
    if isinstance(victim,int):
        ident=victim
        victim=world.objects.get(ident) if world is not None else None
        if victim is None and engine is not None:
            victim=next((obj for obj in engine.get_entities() if getattr(obj,'_id',None)==ident),None)
        if victim is None:victim=SimpleNamespace(_id=ident,_engine=owner)
    attributes=getattr(victim,'attribute_store',None) or getattr(engine,'attributes',None) or attributes_for(victim)
    request=dict(actor=actor._id,target=victim._id,what=what,default=default,
                 owhat=owhat,odefault=odefault,awhat=awhat,args=list(args),applied=False)
    owner.action_requests=getattr(owner,'action_requests',[])
    owner.action_requests.append(request)
    text=attributes.get(victim._id,what) if what else ''
    if text or default:personal_notify(actor,text or default)
    other_text=attributes.get(victim._id,owhat) if owhat else ''
    if (other_text or odefault) and world is not None:
        for ident in world.contents(getattr(actor,'location',-1)):
            if ident not in (actor._id,victim._id):
                personal_notify(world.objects[ident],f'{getattr(actor,"object_name",actor.name)} {other_text or odefault}')
    if awhat:
        action=invoke_hook(owner,awhat.removeprefix('A_'),actor,victim,args)
        request['applied']=action['applied']
    else:request['applied']=True
    return request


def notify_actor(owner, actor, text):
    """Local notify(player), retaining an attempt when a DBref is unavailable."""
    from systems.notifications import personal_notify
    ident = actor if isinstance(actor, int) else getattr(actor, '_id', -1)
    if isinstance(actor, int):
        engine = getattr(owner, '_engine', None)
        world = getattr(engine, 'personnel', None)
        actor = world.objects.get(ident) if world is not None else None
        if actor is None and engine is not None:
            actor = next((obj for obj in engine.get_entities() if getattr(obj, '_id', None) == ident), None)
    request = dict(recipient=ident, message=text, applied=actor is not None)
    owner.admin_requests = getattr(owner, 'admin_requests', [])
    owner.admin_requests.append(request)
    if actor is not None:
        if effect_sink(actor) is None:
            actor.effects = effect_sink(owner)
        personal_notify(actor, text)
    return request
