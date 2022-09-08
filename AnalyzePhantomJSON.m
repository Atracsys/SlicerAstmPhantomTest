function []=AnalyzePhantomJSON(path)
%% AnalyzePhantomJSON
% This function parses the JSON file produced by the ASTM phantom test
% software located at:
% https://github.com/Atracsys/SlicerAstmPhantomTest
% More information at that same URL.
% Sylvain Bernhardt, Atracsys LLC, 2022

filetext = fileread(path);
data = jsondecode(filetext);

locs = {'CL', 'LL', 'RL', 'BL', 'TL'};

resFields={'Single', 'Roll', 'Pitch', 'Yaw', 'Distances'};
out = cell2struct(cell(numel(resFields),1),resFields);

cdiv = data.CalibratedGroundTruth.(sprintf('x%d',data.CentralDivot))';

%% Single point
singFields={'Measurements', 'Accuracy', 'Average', 'Precision'};
out.Single = cell2struct(cell(numel(locs),1),locs);
cats = ["Measurements"; "Accu.Mean"; "Accu.Max"; "Prec.Span"; "Prec.RMS"];
singTable = table(cats);
singPlot_locs = [];
singPlot_mean = [];
singPlot_max = [];
singPlot_rms = [];
for l=1:numel(locs)
    % Create structures
    out.Single.(locs{l}) = cell2struct(cell(numel(singFields),1),singFields);
    accuFields = {'Mean', 'Max'};
    out.Single.(locs{l}).Accuracy = cell2struct(cell(numel(accuFields),1),accuFields);
    precFields = {'Span', 'RMS'};
    out.Single.(locs{l}).Precision = cell2struct(cell(numel(precFields),1),precFields);
    if isfield(data.SinglePointMeasurements, locs{l})
        % Get the actual measured positions
        p = data.SinglePointMeasurements.(locs{l});
        % Number of measurements
        out.Single.(locs{l}).Measurements = size(data.SinglePointMeasurements.(locs{l}),1);
        assert(size(p,1)==out.Single.(locs{l}).Measurements);
        singPlot_locs = [singPlot_locs; l];
        % Accuracy --------------------------
        % One error vector is the vector from the calibrated position of the
        % central divot to the position of the measurement.
        % The bias is the vectorial average of all error vectors.
        % The mean error is the norm of the bias.
        out.Single.(locs{l}).Accuracy.Mean = sqrt(sum(mean(p-cdiv,1).^2,2));
        singPlot_mean = [singPlot_mean; out.Single.(locs{l}).Accuracy.Mean];
        % The max error is the largest norm of an error vector
        errors = sqrt(sum((p-cdiv).^2,2));
        out.Single.(locs{l}).Accuracy.Max = max(errors);
        singPlot_max = [singPlot_max; out.Single.(locs{l}).Accuracy.Max];
        % Average --------------------------
        % The average of all measured positions is the best estimation of the
        % central divot position
        out.Single.(locs{l}).Average = mean(p,1);
        % Precision --------------------------
        % The span is the largest distance between two measured positions
        out.Single.(locs{l}).Precision.Span = 0;
        pairs = nchoosek(1:size(p,1),2);
        for i=1:size(pairs,1)
            p1 = p(pairs(i,1),:); p2 = p(pairs(i,2),:);
            err = sqrt(sum((p1-p2).^2,2));
            out.Single.(locs{l}).Precision.Span = max(out.Single.(locs{l}).Precision.Span, err);
        end
        % The deviation is the distance between a measured position and the
        % average of all measured positions
        % The RMS is the Root-Mean-Square of the deviations (equivalent to the
        % standard deviation of the measured positions in this case)
        devs = sqrt(sum((p-mean(p,1)).^2,2));
        out.Single.(locs{l}).Precision.RMS = sqrt(mean((devs).^2));
        singPlot_rms = [singPlot_rms; out.Single.(locs{l}).Precision.RMS];
        % Dump values in table
        singTable.(locs{l}) = [out.Single.(locs{l}).Measurements;...
            out.Single.(locs{l}).Accuracy.Mean;...
            out.Single.(locs{l}).Accuracy.Max;...
            out.Single.(locs{l}).Precision.Span;...
            out.Single.(locs{l}).Precision.RMS];
    else
        singTable.(locs{l}) = ['-';'-';'-';'-';'-'];
    end
end
singTable
if ishandle(4), close(4); end
if numel(singPlot_locs)>0
    figure(4),
    bar(singPlot_locs, singPlot_mean, 'DisplayName', 'Mean');
    xlim([0 numel(singPlot_locs)+1]);
    xticklabels(locs)
    xlabel("Locations")
    ylabel("Millimeters")
    title('Single Point Error')
    hold on;
    er = errorbar(singPlot_locs, singPlot_mean, singPlot_rms, 'DisplayName', 'RMS');
    er.LineStyle = 'none';
    scatter(singPlot_locs, singPlot_max, 'DisplayName', 'Max', 'MarkerFaceColor',...
        [0.8500 0.3250 0.0980],'MarkerEdgeColor',[0.8500 0.3250 0.0980]);
    legend;
end


%% Rotations
rotations=["Roll", "Pitch", "Yaw"];
for r=1:numel(rotations)
    if ishandle(r), close(r); end
    if numel(fields(data.(rotations(r)+"RotationMeasurements"))) > 0
        figure(r),
        for l=1:numel(locs)
            if isfield(data.(rotations(r)+"RotationMeasurements"), locs{l})
                ang = data.(rotations(r)+"RotationMeasurements").(locs{l})(:,1);
                p = data.(rotations(r)+"RotationMeasurements").(locs{l})(:,2:4);
                % Calculate the deviations from the best estimate of the central
                % divots, i.e. the average of the measured positions from the
                % single point test
                devs = sqrt(sum((p-out.Single.(locs{l}).Average).^2,2));
                plot(ang, devs, 'DisplayName', locs{l}); hold on;
            end
        end
        hold off;
        title("Deviation during " + rotations(r) + " rotation");
        legend;
        ylabel("Deviation (mm)");
        xlabel("Angle (degrees)");
    end
end

%% Distances
distFields={'Num', 'Mean', 'Max', 'RMS'};
out.Dist = cell2struct(cell(numel(locs),1),locs);
cats = ["Num."; "DistErr.Mean"; "DistErr.Max"; "DistErr.RMS"];
distTable = table(cats);
distPlot_locs = [];
distPlot_mean = [];
distPlot_max = [];
distPlot_rms = [];
for l=1:numel(locs)
    % Create structures
    out.Dist.(locs{l}) = cell2struct(cell(numel(distFields),1),distFields);
    if isfield(data.Multi_pointMeasurements, locs{l})
        distPlot_locs = [distPlot_locs; l];
        % Calculate the distances between all combinations of measured
        % positions and compare them to the distances from calibrated positions
        ids = fields(data.Multi_pointMeasurements.(locs{l}));
        N = numel(ids);
        pairs = nchoosek(1:N,2);
        errors = NaN(nchoosek(N,2),1);
        for i=1:size(pairs,1)
            p1 = data.Multi_pointMeasurements.(locs{l}).(ids{pairs(i,1)})';
            p2 = data.Multi_pointMeasurements.(locs{l}).(ids{pairs(i,2)})';
            dist = sqrt(sum((p1-p2).^2,2));
            q1 = data.CalibratedGroundTruth.(ids{pairs(i,1)})';
            q2 = data.CalibratedGroundTruth.(ids{pairs(i,2)})';
            gt = sqrt(sum((q1-q2).^2,2));
            errors(i) = abs(dist-gt);
        end
        % Number of distances
        out.Dist.(locs{l}).Num = numel(errors);
        % Mean
        out.Dist.(locs{l}).Mean = mean(errors);
        distPlot_mean = [distPlot_mean; out.Dist.(locs{l}).Mean];
        % Max
        out.Dist.(locs{l}).Max = max(errors);
        distPlot_max = [distPlot_max; out.Dist.(locs{l}).Max];
        % RMS
        out.Dist.(locs{l}).RMS = sqrt(mean(errors.^2));
        distPlot_rms = [distPlot_rms; out.Dist.(locs{l}).RMS];
        % Dump values in table
        distTable.(locs{l}) = [out.Dist.(locs{l}).Num;...
            out.Dist.(locs{l}).Mean;...
            out.Dist.(locs{l}).Max;...
            out.Dist.(locs{l}).RMS];
    else
        distTable.(locs{l}) = ['-';'-';'-';'-'];
    end
end
distTable
if ishandle(5), close(5); end
if numel(distPlot_locs)>0
    figure(5),
    bar(distPlot_locs, distPlot_mean, 'DisplayName', 'Mean');
    xlim([0 numel(distPlot_locs)+1]);
    xticklabels(locs)
    xlabel("Locations")
    ylabel("Millimeters")
    title('Distances Error')
    hold on;
    er = errorbar(distPlot_locs, distPlot_mean, distPlot_rms, 'DisplayName', 'RMS');
    er.LineStyle = 'none';
    scatter(distPlot_locs, distPlot_max, 'DisplayName', 'Max', 'MarkerFaceColor',...
        [0.8500 0.3250 0.0980],'MarkerEdgeColor',[0.8500 0.3250 0.0980]);
    legend;
end