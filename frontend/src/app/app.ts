import { AfterViewChecked, Component, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import Chart from 'chart.js/auto';
import { environment } from '../environments/environment';

type ChartType = 'bar' | 'line' | 'doughnut' | 'pie' | 'scatter';

interface ChartPoint {
  label: string;
  value: number;
}

interface ChartSpec {
  title: string;
  chart_type: ChartType;
  x_axis?: string;
  y_axis?: string;
  data: ChartPoint[];
}

interface AnalysisSummary {
  file_count: number;
  row_count: number;
  column_count: number;
  join_history?: unknown[];
}

interface AnalysisResult {
  summary: AnalysisSummary;
  top_insights: string[];
  charts: ChartSpec[];
}

@Component({
  selector: 'app-root',
  templateUrl: './app.html',
  styleUrl: './app.css',
  imports: [CommonModule, FormsModule],
})
export class App implements AfterViewChecked, OnDestroy {
  selectedFiles: File[] = [];
  prompt = '';
  generateAll = true;
  status = 'Waiting for files...';
  summary: AnalysisSummary | null = null;
  insights: string[] = [];
  charts: ChartSpec[] = [];

  private chartInstances: Chart[] = [];
  private lastRenderedChartCount = 0;

  onFilesSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.selectedFiles = Array.from(input.files ?? []);
    this.status = this.selectedFiles.length
      ? `${this.selectedFiles.length} file(s) selected`
      : 'Waiting for files...';
  }

  async submit(): Promise<void> {
    if (!this.selectedFiles.length) {
      this.status = 'Please select at least one CSV or Excel file.';
      return;
    }

    this.status = 'Uploading and analyzing files...';

    const formData = new FormData();
    for (const file of this.selectedFiles) {
      formData.append('files', file);
    }

    formData.append('prompt', this.prompt.trim());
    formData.append('generate_all', String(this.generateAll));

    try {
      const response = await fetch(`${environment.apiBaseUrl}/api/analyze`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(() => ({}));
        throw new Error(errorBody.detail ?? 'Unable to analyze files.');
      }

      const result: AnalysisResult = await response.json();
      this.summary = result.summary;
      this.insights = result.top_insights ?? [];
      this.charts = result.charts ?? [];
      this.status = 'Analysis complete';
      this.lastRenderedChartCount = 0;
    } catch (error) {
      this.summary = null;
      this.insights = [];
      this.charts = [];
      this.status = error instanceof Error ? error.message : 'Something went wrong during analysis.';
    }
  }

  ngAfterViewChecked(): void {
    if (this.charts.length > 0 && this.lastRenderedChartCount !== this.charts.length) {
      this.renderCharts();
      this.lastRenderedChartCount = this.charts.length;
    }
  }

  ngOnDestroy(): void {
    this.chartInstances.forEach((chart) => chart.destroy());
    this.chartInstances = [];
  }

  private renderCharts(): void {
    const container = document.getElementById('chart-output');
    if (!container) {
      return;
    }

    this.chartInstances.forEach((chart) => chart.destroy());
    this.chartInstances = [];

    container.innerHTML = this.charts
      .map(
        (chart, index) => `
          <div class="chart-card">
            <h3>${chart.title}</h3>
            <canvas id="chart-${index}" class="chart-canvas"></canvas>
          </div>
        `,
      )
      .join('');

    this.charts.forEach((chart, index) => {
      const canvas = document.getElementById(`chart-${index}`) as HTMLCanvasElement | null;
      if (!canvas) {
        return;
      }

      const context = canvas.getContext('2d');
      if (!context) {
        return;
      }

      const config = {
        type: chart.chart_type || 'bar',
        data: {
          labels: chart.data.map((point) => point.label),
          datasets: [
            {
              label: chart.y_axis ?? 'Value',
              data: chart.data.map((point) => Number(point.value) || 0),
              backgroundColor: ['#60a5fa', '#a78bfa', '#34d399', '#fbbf24', '#f87171', '#2dd4bf'],
              borderColor: '#e2e8f0',
              borderWidth: 1,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              labels: {
                color: '#e2e8f0',
              },
            },
          },
          scales: {
            x: {
              ticks: { color: '#cbd5e1' },
              grid: { color: 'rgba(148,163,184,0.15)' },
            },
            y: {
              ticks: { color: '#cbd5e1' },
              grid: { color: 'rgba(148,163,184,0.15)' },
            },
          },
        },
      };

      this.chartInstances.push(new Chart(context, config as any));
    });
  }
}
