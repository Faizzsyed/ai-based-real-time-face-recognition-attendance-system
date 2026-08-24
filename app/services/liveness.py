"""Limited development pose-sequence challenge; not production anti-spoofing."""
from __future__ import annotations
import random,logging
logger=logging.getLogger("LIVENESS")
class DevelopmentLivenessChallenge:
    def __init__(self,rng=None,observations_per_step=2):
        sides=["left","right"];(rng or random).shuffle(sides);self.steps=["center",*sides];self.index=0;self.fingerprints=set();self.passed=False;self.observations_per_step=max(2,int(observations_per_step));self.streak=0;logger.info("challenge started method=yunet-pose-sequence-dev-v1 steps=%s",len(self.steps))
    @property
    def current(self):return None if self.passed else self.steps[self.index]
    def observe(self,pose,fingerprint):
        if self.passed or not fingerprint or fingerprint in self.fingerprints:return self.passed
        self.fingerprints.add(fingerprint)
        if pose==self.current:
            self.streak+=1
            if self.streak>=self.observations_per_step:
                completed=self.current;self.index+=1;self.streak=0;self.passed=self.index==len(self.steps);logger.info("challenge step passed step=%s",completed)
                if self.passed:logger.info("challenge passed method=yunet-pose-sequence-dev-v1")
        else:self.streak=0
        return self.passed
    def status(self):return {"steps":self.steps,"completed":self.index,"current":self.current,"streak":self.streak,"observationsPerStep":self.observations_per_step,"passed":self.passed,"method":"yunet-pose-sequence-dev-v1"}
