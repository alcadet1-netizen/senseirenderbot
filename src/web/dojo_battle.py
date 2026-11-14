"""Authoritative, deterministic 1v1 simulation. No wallet, DB writes or client physics.

Rules are read from the offline HTML's JSON island: one source for both runtimes.
Rooms are explicitly ephemeral; a restart cancels matches rather than awarding wins.
"""
import json
import math
from html.parser import HTMLParser
from pathlib import Path


class _RulesParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.capture = False
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag == 'script':
            self.capture = dict(attrs).get('id') == 'battleRules'

    def handle_endtag(self, tag):
        if tag == 'script':
            self.capture = False

    def handle_data(self, data):
        if self.capture:
            self.parts.append(data)


def load_rules():
    parser = _RulesParser()
    parser.feed((Path(__file__).resolve().parents[2] / 'index.html').read_text())
    rules = json.loads(''.join(parser.parts))
    assert len(rules['cards']) == 8 and len(rules['levels']) == 6
    return rules


class Battle:
    WIDTH = 960

    def __init__(self, rules):
        self.rules = rules
        self.elapsed = 0.0
        self.winner = None
        self.ended = False
        self.reason = ''
        self.seed = 0
        self.players = [dict(level=1, tower=0, energy=87., hp=1000., maxHp=1000.,
                             charges=[float(c['cd']) if i < 2 else 0. for i, c in enumerate(rules['cards'])],
                             superCd=0., wave=0., waveCount=0, towerCd=1.) for _ in range(2)]
        self.units = [dict(active=False, slot=i) for i in range(rules['unitPool'])]
        self.shots = [dict(active=False) for _ in range(rules['projectilePool'])]

    def multiplier(self):
        tempo = self.rules['tempo']
        return 1 + max(0, min(1, (self.elapsed - tempo['after']) / tempo['ramp']))

    def count(self, side):
        return sum(u['active'] and u['side'] == side for u in self.units)

    def finish(self, winner, reason):
        if not self.ended:
            self.ended, self.winner, self.reason = True, winner, reason

    def command(self, side, action, index=None):
        if self.ended or side not in (0, 1):
            return False
        p = self.players[side]
        if action == 'summon':
            if type(index) is not int or not 0 <= index < len(self.rules['cards']):
                return False
            card = self.rules['cards'][index]
            if (p['level'] < card['level'] or p['energy'] < card['cost'] or
                    p['charges'][index] + 1e-6 < card['cd'] or (index == 5 and self.elapsed < 30)):
                return False
            if not self.spawn(side, card):
                return False
            p['energy'] -= card['cost']
            p['charges'][index] = 0.
        elif action == 'upgrade':
            if p['level'] >= 6:
                return False
            nxt = self.rules['levels'][p['level']]
            if p['energy'] < nxt['cost']:
                return False
            p['energy'] -= nxt['cost']
            p['level'] += 1
            p['maxHp'] += 200
            p['hp'] = min(p['maxHp'], p['hp'] + 200)
        elif action == 'tower':
            if p['tower'] >= len(self.rules['towers']):
                return False
            nxt = self.rules['towers'][p['tower']]
            if p['level'] < nxt['level'] or p['energy'] < nxt['cost']:
                return False
            p['energy'] -= nxt['cost']
            p['tower'] += 1
            p['towerCd'] = .5
        elif action == 'qi':
            if p['superCd'] > 0 or p['energy'] < 20:
                return False
            p['energy'] -= 20
            p['superCd'] = 16 if p['level'] == 6 else max(22, 36 - p['level'] * 2)
            p['wave'], p['waveCount'] = 1., p['waveCount'] + 1
            for u in self.units:
                if u['active'] and u['side'] != side:
                    self.hit(u, (70 + p['level'] * 12) * self.multiplier())
        else:
            return False
        return True

    def spawn(self, side, card):
        if self.count(side) >= self.rules['unitLimit']:
            return False
        slot = next((u for u in self.units if not u['active']), None)
        if slot is None:
            return False
        flying, direction = bool(card.get('flying')), 1 if side == 0 else -1
        entrance = 69 if side == 0 else self.WIDTH - 69
        x = entrance
        for i in range(4):
            x = entrance - direction * i * 18
            if not any(u['active'] and u['side'] == side and u['flying'] == flying and abs(u['x'] - x) < 14 for u in self.units):
                break
        self.seed += 1
        slot.update(active=True, side=side, kind=card['kind'], flying=flying, x=float(x),
                    hp=float(card['hp']), maxHp=float(card['hp']), dmg=card['dmg'],
                    range=card['range'], speed=card['speed'], rate=card['rate'], cool=.2,
                    age=0., flash=0., moving=True, seed=self.seed)
        return True

    def hit(self, unit, damage):
        if not unit['active']:
            return
        unit['hp'] -= damage * (.5 if unit['age'] < .75 else 1)
        if unit['hp'] <= 0:
            unit['active'] = False

    def fire(self, side, x, y, target, damage, kind=2):
        shot = next((s for s in self.shots if not s['active']), None)
        if shot is None:
            self.hit(target, damage)
            return
        shot.update(active=True, x=x, y=y, side=side, target=target['slot'],
                    targetSeed=target['seed'], damage=damage, style=1 if kind == 7 else 2 if kind == 4 else 0, life=2.)

    def step(self, dt):
        if self.ended:
            return
        if not 0 < dt <= .1:
            raise ValueError('Invalid server timestep')
        self.elapsed += dt
        mult = self.multiplier()
        for p in self.players:
            level = self.rules['levels'][p['level'] - 1]
            p['energy'] = min(level['cap'], p['energy'] + dt * level['regen'])
            p['superCd'] = max(0., p['superCd'] - dt)
            p['wave'] = max(0., p['wave'] - dt * 1.3)
            for i, c in enumerate(self.rules['cards']):
                p['charges'][i] = min(c['cd'], p['charges'][i] + dt * level['speed'])
        for u in self.units:
            if not u['active']:
                continue
            u['age'] += dt
            u['cool'] -= dt
            u['flash'] = max(0., u['flash'] - dt)
            side, target, best, blocked, stacked, aura = u['side'], None, math.inf, False, False, 0
            direction = 1 if side == 0 else -1
            for v in self.units:
                if not v['active'] or v is u:
                    continue
                distance = (v['x'] - u['x']) * direction
                if v['side'] != side:
                    if v['flying'] and not u['flying'] and u['range'] <= 75:
                        continue
                    if -5 <= distance < best:
                        target, best = v, distance
                else:
                    same_lane = v['flying'] == u['flying']
                    older_overlap = abs(distance) < .01 and v['seed'] < u['seed']
                    stacked |= same_lane and older_overlap
                    blocked |= same_lane and (distance > 0 or older_overlap) and distance < 18 and v['range'] <= u['range']
                    if v['kind'] == 1 and abs(v['x'] - u['x']) < 100:
                        aura = 2 + (2 if self.players[side]['level'] >= 4 else 0)
            base_distance = u['x'] - 50 if side else self.WIDTH - 50 - u['x']
            base_range = base_distance <= u['range']
            inside = target and (target['x'] < 69 if side else target['x'] > self.WIDTH - 69)
            if base_range and (target is None or base_distance < best or inside):
                target = None
            if ((target is not None and best <= u['range']) or (target is None and base_range)) and not (stacked and u['range'] <= 75):
                u['moving'] = False
                if u['cool'] <= 0:
                    u['cool'], u['flash'] = u['rate'], .16
                    damage = (u['dmg'] + aura) * mult
                    if u['kind'] == 4:
                        for ally in self.units:
                            if ally['active'] and ally['side'] == side and abs(ally['x'] - u['x']) < 110:
                                ally['hp'] = min(ally['maxHp'], ally['hp'] + 12)
                    if target is not None:
                        if u['range'] > 75:
                            self.fire(side, u['x'], -64. if u['flying'] else 0., target, damage, u['kind'])
                        else:
                            self.hit(target, damage)
                    else:
                        other = self.players[1 - side]
                        other['hp'] = max(0., other['hp'] - damage)
            elif not blocked and u['age'] > .25:
                u['moving'] = True
                u['x'] += direction * max(0., min(u['speed'] * dt, best - 24 if target is not None else base_distance - 22))
            else:
                u['moving'] = False
        for s in self.shots:
            if not s['active']:
                continue
            s['life'] -= dt
            target = self.units[s['target']]
            if s['life'] <= 0 or not target['active'] or target['seed'] != s['targetSeed']:
                s['active'] = False
                continue
            dx, dy = target['x'] - s['x'], (-64 if target['flying'] else 0) - s['y']
            distance, step = math.hypot(dx, dy), 260 * dt
            if distance < step + 3:
                self.hit(target, s['damage'])
                s['active'] = False
            else:
                s['x'] += dx / distance * step
                s['y'] += dy / distance * step
        for side, p in enumerate(self.players):
            if not p['tower']:
                continue
            p['towerCd'] -= dt
            if p['towerCd'] > 0:
                continue
            tower = self.rules['towers'][p['tower'] - 1]
            x = 52 if side == 0 else self.WIDTH - 52
            targets = [u for u in self.units if u['active'] and u['side'] != side and abs(u['x'] - x) < tower['range']]
            if targets:
                target = min(targets, key=lambda u: abs(u['x'] - x))
                self.fire(side, x, -70., target, tower['damage'] * mult)
                p['towerCd'] = tower['rate']
        if any(p['hp'] <= 0 for p in self.players):
            winner = None if all(p['hp'] <= 0 for p in self.players) else (0 if self.players[1]['hp'] <= 0 else 1)
            self.finish(winner, 'castle')
        if self.elapsed >= 1200:
            self.finish(None, 'time_limit')

    def snapshot(self):
        # Never serialize inactive pools, internal damage or client-supplied state.
        return dict(elapsed=round(self.elapsed, 3), winner=self.winner, reason=self.reason,
                    players=[{k: (round(v, 3) if isinstance(v, float) else v) for k, v in p.items() if k != 'towerCd'} for p in self.players],
                    units=[{k: (round(v, 3) if isinstance(v, float) else v) for k, v in u.items() if k in {'slot', 'side', 'kind', 'flying', 'x', 'hp', 'maxHp', 'age', 'flash', 'moving', 'seed'}} for u in self.units if u['active']],
                    shots=[{k: (round(v, 3) if isinstance(v, float) else v) for k, v in s.items() if k != 'damage'} for s in self.shots if s['active']])
