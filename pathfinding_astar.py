"""
PATHFINDING COM A* (A-STAR)

Calcula rota navegável contornando obstáculos
"""

import cv2
import numpy as np
import heapq
from typing import List, Tuple, Optional


class AStarPathfinder:
    """Pathfinding A* para navegação no mapa"""

    def __init__(self, mapa_colorido, wall_margin=5):
        """
        Args:
            mapa_colorido: Mapa BGR onde áreas coloridas são walkáveis
            wall_margin: Margem de segurança das paredes em pixels (padrão: 5)
        """
        self.mapa = mapa_colorido
        self.height, self.width = mapa_colorido.shape[:2]
        self.wall_margin = wall_margin

        # Criar máscara de walkability (1 = walkável, 0 = não walkável)
        print("   Criando mapa de walkability...")
        self.walkable_mask = self._create_walkable_mask()

        # Aplicar margem de segurança (dilatando paredes)
        if self.wall_margin > 0:
            print(f"   Aplicando margem de seguranca: {self.wall_margin}px (dilatando paredes)...")
            self.walkable_mask = self._apply_wall_margin(self.walkable_mask, self.wall_margin)

        # Contar áreas walkáveis
        walkable_count = np.sum(self.walkable_mask > 0)
        total_pixels = self.walkable_mask.size
        percent = (walkable_count / total_pixels) * 100
        print(f"   Areas walkaveis: {walkable_count}/{total_pixels} ({percent:.1f}%)")

    def _create_walkable_mask(self):
        """Cria máscara binária: 1 = walkável, 0 = obstáculo

        IMPORTANTE: Usa mapa COLORIDO (MINIMAPA CERTOPRETO.png) onde:
        - COLORIDO (pixels com cor, qualquer RGB > 10) = walkable (chão do jogo)
        - PRETO (pixels escuros, RGB <= 10) = obstáculo/parede/fora do mapa
        
        Isso é o contrário do mapa P&B:
        - No mapa P&B: PRETO = walkable, BRANCO = parede
        - No mapa COLORIDO: COLORIDO = walkable, PRETO = parede
        """
        # Verificar se está em BGR (3 canais) ou grayscale (1 canal)
        if len(self.mapa.shape) == 2:
            # Se for grayscale, converter para BGR primeiro
            mapa_bgr = cv2.cvtColor(self.mapa, cv2.COLOR_GRAY2BGR)
        else:
            # Já está em BGR
            mapa_bgr = self.mapa

        # Separar canais BGR
        b, g, r = cv2.split(mapa_bgr)
        
        # Walkável = COLORIDO (pelo menos um canal > 10)
        # Não walkável = PRETO (todos os canais <= 10)
        # Criar máscara: 1 = walkable (colorido), 0 = não walkable (preto)
        mask = np.zeros((self.height, self.width), dtype=np.uint8)
        
        # Se pelo menos um canal tem valor > 10, é colorido (walkable)
        mask[(b > 10) | (g > 10) | (r > 10)] = 1
        
        # Alternativa: usar média dos canais
        # Se média > 10, é colorido (walkable)
        # gray = cv2.cvtColor(mapa_bgr, cv2.COLOR_BGR2GRAY)
        # mask[gray > 10] = 1

        return mask

    def _apply_wall_margin(self, walkable_mask, margin):
        """
        Aplica margem de segurança dilatando as paredes (obstáculos)
        
        Isso faz com que o pathfinding evite caminhos muito próximos às paredes,
        reduzindo o risco de cliques acidentais em paredes.
        
        Args:
            walkable_mask: Máscara binária (1 = walkable, 0 = parede)
            margin: Margem em pixels (raio de dilatação)
        
        Returns:
            Máscara com paredes dilatadas
        """
        # Paredes = 0, walkable = 1
        # Para dilatar paredes, precisamos inverter, dilatar, e inverter de volta
        # Cria máscara de paredes (0 = parede, 255 = walkable)
        wall_mask = (1 - walkable_mask) * 255
        
        # Criar kernel circular para dilatação
        kernel_size = margin * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kernel_size, kernel_size))
        
        # Dilatar paredes (aumentar área de não-walkable)
        dilated_walls = cv2.dilate(wall_mask.astype(np.uint8), kernel, iterations=1)
        
        # Converter de volta para máscara binária (1 = walkable, 0 = parede)
        # Se pixel é 255 (parede dilatada), vira 0 (não walkable)
        # Se pixel é 0 (walkable), vira 1 (walkable)
        new_walkable_mask = (dilated_walls == 0).astype(np.uint8)
        
        return new_walkable_mask

    def is_walkable(self, x: int, y: int) -> bool:
        """Verifica se posição é walkável"""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return False
        return self.walkable_mask[y, x] > 0

    def get_neighbors(self, x: int, y: int) -> List[Tuple[int, int, float]]:
        """
        Retorna vizinhos walkáveis com custo

        Returns:
            Lista de (x, y, custo)
        """
        neighbors = []

        # 8 direções (4 cardinais + 4 diagonais)
        directions = [
            (0, -1, 1.0),   # Norte
            (1, 0, 1.0),    # Leste
            (0, 1, 1.0),    # Sul
            (-1, 0, 1.0),   # Oeste
            (1, -1, 1.4),   # Nordeste (diagonal)
            (1, 1, 1.4),    # Sudeste
            (-1, 1, 1.4),   # Sudoeste
            (-1, -1, 1.4),  # Noroeste
        ]

        for dx, dy, cost in directions:
            nx, ny = x + dx, y + dy

            if self.is_walkable(nx, ny):
                neighbors.append((nx, ny, cost))

        return neighbors

    def heuristic(self, x1: int, y1: int, x2: int, y2: int) -> float:
        """Distância euclidiana como heurística"""
        return np.sqrt((x2 - x1)**2 + (y2 - y1)**2)

    def find_path(self, start_x: int, start_y: int, goal_x: int, goal_y: int,
                  max_iterations: int = 50000) -> Optional[List[Tuple[int, int]]]:
        """
        Encontra caminho usando A*

        Args:
            start_x, start_y: Posição inicial
            goal_x, goal_y: Posição destino
            max_iterations: Limite de iterações

        Returns:
            Lista de (x, y) representando o caminho, ou None se não encontrar
        """
        # Verificar se início e fim são walkáveis
        if not self.is_walkable(start_x, start_y):
            print(f"      ERRO: Posicao inicial ({start_x}, {start_y}) nao e walkavel!")
            return None

        if not self.is_walkable(goal_x, goal_y):
            print(f"      ERRO: Posicao destino ({goal_x}, {goal_y}) nao e walkavel!")
            # Tentar encontrar ponto walkável próximo ao destino
            for raio in range(5, 100, 5):
                for angulo in range(0, 360, 15):
                    rad = np.radians(angulo)
                    test_x = int(goal_x + raio * np.cos(rad))
                    test_y = int(goal_y + raio * np.sin(rad))

                    if self.is_walkable(test_x, test_y):
                        print(f"      Destino ajustado para: ({test_x}, {test_y})")
                        goal_x, goal_y = test_x, test_y
                        break
                else:
                    continue
                break
            else:
                print(f"      ERRO: Nenhum ponto walkavel encontrado proximo ao destino!")
                return None

        # A* setup
        start = (start_x, start_y)
        goal = (goal_x, goal_y)

        # Priority queue: (f_score, counter, (x, y))
        counter = 0
        open_set = [(0, counter, start)]
        counter += 1

        came_from = {}
        g_score = {start: 0}
        f_score = {start: self.heuristic(start_x, start_y, goal_x, goal_y)}

        open_set_hash = {start}
        iterations = 0

        while open_set and iterations < max_iterations:
            iterations += 1

            # Pegar nó com menor f_score
            _, _, current = heapq.heappop(open_set)
            open_set_hash.discard(current)

            # Chegou no destino?
            if current == goal:
                # Reconstruir caminho
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start)
                path.reverse()

                print(f"      Caminho encontrado: {len(path)} pontos ({iterations} iteracoes)")
                return path

            # Explorar vizinhos
            cx, cy = current
            for nx, ny, move_cost in self.get_neighbors(cx, cy):
                neighbor = (nx, ny)
                tentative_g = g_score[current] + move_cost

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f = tentative_g + self.heuristic(nx, ny, goal_x, goal_y)
                    f_score[neighbor] = f

                    if neighbor not in open_set_hash:
                        heapq.heappush(open_set, (f, counter, neighbor))
                        counter += 1
                        open_set_hash.add(neighbor)

        print(f"      ERRO: Caminho nao encontrado apos {iterations} iteracoes!")
        return None

    def simplify_path(self, path: List[Tuple[int, int]],
                     max_distance: int = 100) -> List[Tuple[int, int]]:
        """
        Simplifica caminho removendo pontos intermediários desnecessários

        Args:
            path: Caminho completo pixel a pixel
            max_distance: Distância máxima entre waypoints

        Returns:
            Caminho simplificado
        """
        if not path or len(path) <= 2:
            return path

        simplified = [path[0]]
        current_idx = 0
        min_distance = 50  # Distância MÍNIMA entre waypoints (evitar pontos muito próximos)

        while current_idx < len(path) - 1:
            x1, y1 = path[current_idx]
            best_idx = None

            # Tentar pular o máximo possível mantendo linha de visão
            # Procura de trás para frente para encontrar o ponto MAIS DISTANTE primeiro
            for test_idx in range(len(path) - 1, current_idx, -1):
                x2, y2 = path[test_idx]

                # Calcular distância
                dist = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)

                # Ignorar se muito perto (< min_distance)
                if dist < min_distance:
                    continue

                # Passou do limite máximo?
                if dist > max_distance:
                    continue

                # Verificar se tem linha de visão (todos pontos intermediários são walkáveis)
                if self._has_line_of_sight(x1, y1, x2, y2):
                    best_idx = test_idx
                    break

            # Se não encontrou nenhum ponto válido (>= min_distance com linha de visão)
            # Pegar o ponto que esteja pelo menos a min_distance
            if best_idx is None:
                for test_idx in range(current_idx + 1, len(path)):
                    x2, y2 = path[test_idx]
                    dist = np.sqrt((x2 - x1)**2 + (y2 - y1)**2)

                    if dist >= min_distance:
                        best_idx = test_idx
                        break

            # Último recurso: se ainda não achou, pegar o próximo ponto
            if best_idx is None:
                best_idx = current_idx + 1

            simplified.append(path[best_idx])
            current_idx = best_idx

        print(f"      Caminho simplificado: {len(path)} -> {len(simplified)} pontos")
        return simplified

    def _has_line_of_sight(self, x1: int, y1: int, x2: int, y2: int) -> bool:
        """Verifica se há linha de visão entre dois pontos (Bresenham)"""
        # Bresenham's line algorithm
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        sx = 1 if x1 < x2 else -1
        sy = 1 if y1 < y2 else -1
        err = dx - dy

        x, y = x1, y1

        while True:
            # Verificar se ponto atual é walkável
            if not self.is_walkable(x, y):
                return False

            if x == x2 and y == y2:
                break

            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy

        return True


if __name__ == "__main__":
    # Teste
    print("=" * 70)
    print("TESTE DE PATHFINDING A*")
    print("=" * 70)

    import sys
    sys.path.insert(0, '.')
    from gps_ncc_realtime import GPSRealtimeNCC

    # Carregar mapa
    gps = GPSRealtimeNCC()

    # Criar pathfinder
    print("\nCriando pathfinder...")
    pathfinder = AStarPathfinder(gps.mapa_colorido)

    # Obter posição atual
    print("\nObtendo posicao atual...")
    pos = gps.get_current_position(keep_map_open=False, verbose=False)

    # Testar pathfinding
    print(f"\nTestando pathfinding:")
    print(f"   Inicio: ({pos['x']}, {pos['y']})")
    print(f"   Destino: (374, 1342) - Deserto")

    path = pathfinder.find_path(pos['x'], pos['y'], 374, 1342)

    if path:
        print(f"\n   Caminho completo: {len(path)} pontos")

        # Simplificar
        simplified = pathfinder.simplify_path(path, max_distance=100)
        print(f"   Waypoints: {len(simplified)}")

        print("\n   Primeiros 10 waypoints:")
        for i, (x, y) in enumerate(simplified[:10], 1):
            print(f"      {i}. ({x}, {y})")
    else:
        print("\n   Falhou ao encontrar caminho!")

    print("\n" + "=" * 70)
